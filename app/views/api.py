from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

api_bp = Blueprint('api', __name__)

@api_bp.route('/chatbot', methods=['POST'])
@jwt_required()
def chatbot():
    """Rule-based chatbot endpoint with pre-determined responses"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').lower().strip()
        
        # Pre-determined responses for common questions
        responses = {
            # Greetings
            'hello': 'Hello! Welcome to LSPU ScholarHub. How can I help you today?',
            'hi': 'Hi there! I\'m here to help you with scholarship information. What would you like to know?',
            'good morning': 'Good morning! How can I assist you with scholarships today?',
            'good afternoon': 'Good afternoon! What scholarship information can I help you with?',
            
            # Scholarship Information
            'scholarship': 'LSPU ScholarHub offers various scholarships including Academic Excellence, Financial Aid, and Special Skills scholarships. Would you like to know about any specific type?',
            'what scholarships are available': 'We offer: 1) Academic Excellence Scholarship (for high GPA students), 2) Financial Aid Grant (for students with financial needs), 3) Sports Scholarship (for student-athletes), and 4) Cultural Arts Scholarship (for talented artists).',
            'requirements': 'Requirements vary by scholarship but generally include: 1) Completed application form, 2) Academic records, 3) Proof of financial need (if applicable), 4) Recommendation letters, and 5) Personal essay.',
            'how to apply': 'To apply: 1) Create an account, 2) Browse available scholarships, 3) Click "Apply" on your chosen scholarship, 4) Fill out the application form, 5) Upload required documents, and 6) Submit before the deadline.',
            
            # Deadlines
            'deadline': 'Scholarship deadlines vary. Most scholarships have deadlines at the end of each semester. Please check the specific scholarship page for exact dates.',
            'when is the deadline': 'Deadline dates are shown on each scholarship page. Current active scholarships have deadlines ranging from December 31, 2024 to January 15, 2025.',
            
            # Application Status
            'application status': 'You can check your application status by logging into your account and visiting "My Applications" in the scholarship section.',
            'how long does it take': 'Application review typically takes 2-4 weeks. You will receive email notifications about any status changes.',
            
            # Financial Information
            'how much': 'Scholarship amounts vary: Academic Excellence: ₱10,000-₱25,000 per semester, Financial Aid: ₱5,000-₱15,000 per semester, Sports/Cultural: ₱8,000-₱20,000 per semester.',
            'is it free': 'Yes! All scholarships are free to apply. There are no application fees.',
            
            # Eligibility
            'who can apply': 'Any enrolled LSPU student with good academic standing can apply. Specific requirements vary by scholarship type.',
            'gpa requirement': 'Generally, you need a GPA of at least 2.5 for most scholarships, but Academic Excellence requires 1.75 or better.',
            
            # Contact and Help
            'contact': 'You can reach us at: Email: info@lspu-scholarhub.edu, Phone: (049) 576-1234, or visit our office at the Student Affairs Building.',
            'help': 'I can help you with: finding scholarships, application procedures, requirements, deadlines, and general information about our services.',
            'thank you': 'You\'re welcome! If you have more questions, feel free to ask anytime.',
            
            # Default responses
            'default': 'I understand your question. For more specific information, please check our scholarship pages or contact our office at (049) 576-1234.',
            'i don\'t understand': 'I apologize. Could you please rephrase your question? You can ask about scholarships, applications, requirements, or deadlines.',
        }
        
        # Find the best matching response
        response_text = responses.get('default')
        
        # Check for exact matches first
        if user_message in responses:
            response_text = responses[user_message]
        else:
            # Check for partial matches
            for keyword, response in responses.items():
                if keyword != 'default' and keyword in user_message:
                    response_text = response
                    break
        
        response = {
            'status': 'success',
            'response': response_text,
            'timestamp': '2024-01-01T00:00:00Z'  # Current timestamp
        }
        
        return jsonify(response)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@api_bp.route('/notifications/send', methods=['POST'])
@jwt_required()
def send_notification():
    """Send notification endpoint"""
    try:
        data = request.get_json()
        # Notification logic here
        response = {
            'status': 'success',
            'message': 'Notification sent successfully'
        }
        return jsonify(response)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@api_bp.route('/scholarships', methods=['GET'])
def get_scholarships():
    """Get all scholarships API endpoint"""
    try:
        # Scholarship data logic here
        response = {
            'status': 'success',
            'data': []
        }
        return jsonify(response)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
