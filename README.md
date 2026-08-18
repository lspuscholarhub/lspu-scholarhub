# LSPU ScholarHub: AI-Enabled Scholarship Management System

A comprehensive web-based scholarship management and monitoring system with AI chatbot capabilities and multi-channel notifications, built with Flask and MySQL.

## 🚀 Features

- **User Authentication & Authorization**: Secure login system with JWT tokens
- **Scholarship Management**: Create, view, and manage scholarship opportunities
- **Application System**: Online scholarship application with document upload
- **AI Chatbot**: Intelligent assistant for scholarship inquiries
- **Multi-Channel Notifications**: Email, SMS, and in-app notifications
- **Admin Dashboard**: Comprehensive management interface
- **Responsive Design**: Mobile-friendly interface

## 🛠️ Tech Stack

- **Backend**: Flask (Python)
- **Database**: MySQL with SQLAlchemy ORM
- **Frontend**: HTML5, CSS3, JavaScript
- **Authentication**: JWT (JSON Web Tokens)
- **Notifications**: Flask-Mail, Twilio (optional)
- **AI Integration**: OpenAI API (optional)

## 📁 Project Structure

```
capstone/
├── app/
│   ├── __init__.py              # Application factory
│   ├── models/                  # Database models
│   │   ├── __init__.py
│   │   ├── user.py             # User model
│   │   ├── scholarship.py      # Scholarship models
│   │   └── notification.py     # Notification model
│   ├── views/                   # Route handlers (Blueprints)
│   │   ├── __init__.py
│   │   ├── main.py             # Main routes
│   │   ├── auth.py             # Authentication routes
│   │   ├── scholarship.py      # Scholarship routes
│   │   ├── admin.py            # Admin routes
│   │   └── api.py              # API routes
│   ├── templates/               # HTML templates
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── auth/
│   │   ├── scholarship/
│   │   └── admin/
│   └── static/                  # Static files
│       ├── css/
│       ├── js/
│       ├── images/
│       └── uploads/
├── config/
│   └── config.py               # Configuration settings
├── migrations/                  # Database migrations
├── tests/                      # Test files
├── .env                        # Environment variables
├── .gitignore
├── requirements.txt            # Python dependencies
├── run.py                      # Application entry point
├── app.py                      # Legacy entry point
└── README.md
```

## 🚀 Setup Instructions

### Prerequisites

- Python 3.8+
- MySQL 5.7+ or 8.0+
- pip (Python package installer)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd capstone
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Database Setup

#### Create MySQL Database

```sql
mysql -u root -p
CREATE DATABASE lspu_scholarhub;
CREATE USER 'scholarhub_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON lspu_scholarhub.* TO 'scholarhub_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

#### Configure Environment Variables

1. Copy the `.env` file and update the database credentials:

```env
# Database Configuration
DATABASE_URL=mysql+pymysql://scholarhub_user:your_password@localhost/lspu_scholarhub
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=scholarhub_user
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=lspu_scholarhub

# Flask Configuration
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=your-secret-key-here-change-in-production

# JWT Configuration
JWT_SECRET_KEY=your-jwt-secret-key-here

# Email Configuration (optional)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# AI Configuration (optional)
OPENAI_API_KEY=your-openai-api-key-here
```

### 5. Initialize Database

```bash
# Initialize Flask-Migrate
flask db init

# Create initial migration
flask db migrate -m "Initial migration"

# Apply migrations
flask db upgrade
```

### 6. Run the Application

```bash
# Development mode
python run.py

# Or using Flask
flask run
```

The application will be available at `http://localhost:5000`

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_ENV` | Environment (development/production) | `development` |
| `SECRET_KEY` | Flask secret key | `dev-secret-key` |
| `DATABASE_URL` | MySQL connection string | - |
| `JWT_SECRET_KEY` | JWT signing key | `jwt-secret-string` |
| `MAIL_SERVER` | SMTP server for emails | - |
| `OPENAI_API_KEY` | OpenAI API key for chatbot | - |

### Database Configuration

The application uses SQLAlchemy ORM with MySQL. Ensure your MySQL server is running and the database is created before starting the application.

## 📱 API Endpoints

### Authentication
- `POST /auth/login` - User login
- `POST /auth/register` - User registration
- `GET /auth/profile` - Get user profile (JWT required)

### Scholarships
- `GET /scholarship/` - List all scholarships
- `GET /scholarship/<id>` - Get scholarship details
- `POST /scholarship/apply/<id>` - Apply for scholarship (JWT required)

### API
- `POST /api/chatbot` - AI chatbot endpoint (JWT required)
- `GET /api/scholarships` - Get scholarships (JSON API)
- `POST /api/notifications/send` - Send notification

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_auth.py
```

## 🚀 Deployment

### Production Setup

1. Set environment variables for production
2. Use a production WSGI server (Gunicorn):
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 run:app
   ```

3. Configure reverse proxy (Nginx/Apache)
4. Set up SSL certificates
5. Configure logging and monitoring

## 🔒 Security Considerations

- Change default secret keys in production
- Use HTTPS in production
- Implement rate limiting for API endpoints
- Validate and sanitize all user inputs
- Use parameterized queries to prevent SQL injection
- Implement CORS policies for API endpoints

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📝 License

This project is part of a thesis submission for LSPU.

## 📞 Support

For support and questions, please contact the development team.

## 🔄 Future Enhancements

- Real-time notifications with WebSocket
- Advanced analytics and reporting
- Mobile application
- Integration with student information systems
- Machine learning for scholarship matching
- Blockchain for certificate verification
