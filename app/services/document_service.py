"""
Document Management Service for LSPU ScholarHub
Handles file uploads, validation, and storage
"""

import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app
import logging

logger = logging.getLogger(__name__)

class DocumentService:
    def __init__(self):
        # Allowed file extensions
        self.ALLOWED_EXTENSIONS = {
            'transcript':       ['pdf', 'jpg', 'jpeg', 'png'],
            'good_moral':       ['pdf', 'jpg', 'jpeg', 'png'],
            'birth_cert':       ['pdf', 'jpg', 'jpeg', 'png'],
            'awards':           ['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'],
            'application_form': ['pdf', 'doc', 'docx'],
            'id_card':          ['pdf', 'jpg', 'jpeg', 'png'],
            'parents_income':   ['pdf', 'doc', 'docx'],
            'certificate':      ['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'],
            'registration':     ['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'],
            'general':          ['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'],
        }
        
        # Maximum file sizes (in bytes)
        self.MAX_FILE_SIZES = {
            'pdf': 5 * 1024 * 1024,  # 5MB
            'doc': 5 * 1024 * 1024,  # 5MB
            'docx': 5 * 1024 * 1024, # 5MB
            'jpg': 2 * 1024 * 1024,  # 2MB
            'jpeg': 2 * 1024 * 1024, # 2MB
            'png': 2 * 1024 * 1024   # 2MB
        }
    
    def allowed_file(self, filename, category):
        """Check if file is allowed for the category"""
        if not filename:
            return False
        
        # Get file extension
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        
        # Check if extension is allowed for this category
        if category in self.ALLOWED_EXTENSIONS:
            return ext in self.ALLOWED_EXTENSIONS[category]
        
        return False
    
    def validate_file_size(self, filename, file_size):
        """Validate file size"""
        if not filename:
            return False, "Invalid filename"
        
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        
        if ext in self.MAX_FILE_SIZES:
            max_size = self.MAX_FILE_SIZES[ext]
            if file_size > max_size:
                return False, f"File size too large. Maximum size is {max_size // (1024*1024)}MB"
        
        return True, "File size valid"
    
    def generate_unique_filename(self, original_filename, user_id, category):
        """Generate unique filename for storage"""
        # Get file extension
        ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
        
        # Generate unique identifier
        unique_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create filename: category_userID_timestamp_uniqueID.ext
        filename = f"{category}_{user_id}_{timestamp}_{unique_id}.{ext}"
        
        return filename
    
    def save_file(self, file, user_id, category):
        """Save uploaded file with validation"""
        try:
            if not file or file.filename == '':
                return {'success': False, 'message': 'No file selected'}
            
            original_filename = file.filename
            file_size = len(file.read())
            file.seek(0)  # Reset file pointer
            
            # Validate file extension
            if not self.allowed_file(original_filename, category):
                return {
                    'success': False, 
                    'message': f'File type not allowed for {category}. Allowed types: {", ".join(self.ALLOWED_EXTENSIONS.get(category, []))}'
                }
            
            # Validate file size
            size_valid, size_message = self.validate_file_size(original_filename, file_size)
            if not size_valid:
                return {'success': False, 'message': size_message}
            
            # Generate unique filename
            unique_filename = self.generate_unique_filename(original_filename, user_id, category)
            
            # Create upload directory if it doesn't exist
            upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'documents', str(user_id))
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save file
            file_path = os.path.join(upload_dir, unique_filename)
            file.save(file_path)
            
            # Get file info
            file_info = {
                'original_filename': original_filename,
                'stored_filename': unique_filename,
                'file_path': file_path,
                'file_size': file_size,
                'category': category,
                'uploaded_at': datetime.utcnow().isoformat(),  # ISO string — safe for JSON columns
                'file_type': original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
            }
            
            logger.info(f"File saved successfully: {unique_filename} for user {user_id}")
            
            return {
                'success': True,
                'message': 'File uploaded successfully',
                'file_info': file_info
            }
            
        except Exception as e:
            logger.error(f"Error saving file: {str(e)}")
            return {'success': False, 'message': f'Error saving file: {str(e)}'}
    
    def delete_file(self, file_path):
        """Delete file from storage"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"File deleted: {file_path}")
                return {'success': True, 'message': 'File deleted successfully'}
            else:
                return {'success': False, 'message': 'File not found'}
        except Exception as e:
            logger.error(f"Error deleting file: {str(e)}")
            return {'success': False, 'message': f'Error deleting file: {str(e)}'}
    
    def get_file_info(self, file_path):
        """Get file information"""
        try:
            if not os.path.exists(file_path):
                return None
            
            stat = os.stat(file_path)
            return {
                'file_path': file_path,
                'file_size': stat.st_size,
                'created_at': datetime.fromtimestamp(stat.st_ctime),
                'modified_at': datetime.fromtimestamp(stat.st_mtime),
                'file_type': file_path.rsplit('.', 1)[1].lower() if '.' in file_path else ''
            }
        except Exception as e:
            logger.error(f"Error getting file info: {str(e)}")
            return None
    
    def validate_application_documents(self, documents):
        """Validate all required documents for scholarship application"""
        required_documents = {
            'transcript': 'Transcript of Records',
            'good_moral': 'Certificate of Good Moral',
            'application_essay': 'Application Essay'
        }
        
        validation_results = {
            'valid': True,
            'missing': [],
            'invalid': [],
            'valid_documents': []
        }
        
        for doc_category, doc_name in required_documents.items():
            doc_found = False
            
            for doc in documents:
                if doc.get('category') == doc_category:
                    doc_found = True
                    
                    # Validate file
                    if not self.allowed_file(doc.get('original_filename', ''), doc_category):
                        validation_results['invalid'].append({
                            'category': doc_category,
                            'name': doc_name,
                            'filename': doc.get('original_filename', ''),
                            'error': f'Invalid file type for {doc_name}'
                        })
                        validation_results['valid'] = False
                    else:
                        validation_results['valid_documents'].append({
                            'category': doc_category,
                            'name': doc_name,
                            'filename': doc.get('original_filename', ''),
                            'size': doc.get('file_size', 0)
                        })
                    break
            
            if not doc_found:
                validation_results['missing'].append({
                    'category': doc_category,
                    'name': doc_name
                })
                validation_results['valid'] = False
        
        return validation_results
    
    def get_user_documents(self, user_id):
        """Get all documents for a user"""
        try:
            user_doc_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'documents', str(user_id))
            
            if not os.path.exists(user_doc_dir):
                return []
            
            documents = []
            for filename in os.listdir(user_doc_dir):
                file_path = os.path.join(user_doc_dir, filename)
                file_info = self.get_file_info(file_path)
                
                if file_info:
                    # Parse filename to get category
                    parts = filename.split('_')
                    category = parts[0] if len(parts) > 0 else 'unknown'
                    
                    documents.append({
                        'category': category,
                        'filename': filename,
                        'file_path': file_path,
                        'file_size': file_info['file_size'],
                        'uploaded_at': file_info['created_at'],
                        'file_type': file_info['file_type']
                    })
            
            # Sort by upload date (newest first)
            documents.sort(key=lambda x: x['uploaded_at'], reverse=True)
            
            return documents
            
        except Exception as e:
            logger.error(f"Error getting user documents: {str(e)}")
            return []
    
    def create_document_record(self, user_id, file_info, application_id=None):
        """Create document record in database"""
        try:
            from app import db
            from app.models import Document
            
            document = Document(
                user_id=user_id,
                application_id=application_id,
                original_filename=file_info['original_filename'],
                stored_filename=file_info['stored_filename'],
                file_path=file_info['file_path'],
                file_size=file_info['file_size'],
                category=file_info['category'],
                file_type=file_info['file_type'],
                uploaded_at=file_info['uploaded_at'],
                is_verified=False
            )
            
            db.session.add(document)
            db.session.commit()
            
            logger.info(f"Document record created: {file_info['stored_filename']}")
            return document
            
        except Exception as e:
            logger.error(f"Error creating document record: {str(e)}")
            db.session.rollback()
            return None

# Global document service instance
document_service = DocumentService()
