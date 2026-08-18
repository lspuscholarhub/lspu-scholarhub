# Legacy app.py - Use run.py for running the application
# This file is kept for backward compatibility

from run import app

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)