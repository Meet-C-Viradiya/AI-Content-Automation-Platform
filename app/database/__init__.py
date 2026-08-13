from app.database.database import Base, engine
from app.database.models import Job, AutomationLog, GeneratedContent


def init_db():
    Base.metadata.create_all(bind=engine)