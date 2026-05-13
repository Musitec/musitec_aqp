from dotenv import load_dotenv
import os

load_dotenv()

class Settings:
    PROJECT_NAME = "Musitec Peru"
    SECRET_KEY = os.getenv("SECRET_KEY")
    MONGO_URL = os.getenv("MONGO_URI")
    PERSONAL_EMAIL = os.getenv("PERSONAL_EMAIL")
    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASS = os.getenv("EMAIL_PASS")
    DEFAULT_FROM_EMAIL = EMAIL_USER
    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = os.getenv("MAIL_PORT")
    JWT_SECRET = os.getenv("JWT_SECRET")
    ALGORITHM = "HS256"
    musitec_db = "musitec_db"
    CLOUDINARY_CLOUD_NAME= os.getenv("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY=os.getenv("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET=os.getenv("CLOUDINARY_API_SECRET")
    ENV = os.getenv("ENV", "development")
    RUN_SCHEDULER = os.getenv("RUN_SCHEDULER", "false")
settings = Settings()