from application import Application

# # Module level app instance for uvicorn reload functionality
_app_instance = None

def get_app():
    """Factory function to get or create the application instance"""
    global _app_instance
    if _app_instance is None:
        _app_instance = Application()
    return _app_instance.app

# Create the app instance for uvicorn import string usage
app = get_app()

if __name__ == "__main__":
    app = Application().app
