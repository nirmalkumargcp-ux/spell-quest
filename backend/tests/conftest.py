import os
import tempfile

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("SEED_ON_START", "0")

from app.models import Base, Child, Family, Subject  # noqa: E402
from app.seed.seed import seed_all  # noqa: E402


@pytest.fixture()
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = Session()
    seed_all(session)
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.unlink(path)


@pytest.fixture()
def subject(db) -> Subject:
    return db.scalar(select(Subject).where(Subject.slug == "english"))


@pytest.fixture()
def child(db) -> Child:
    family = Family(name="Test Family")
    db.add(family)
    db.flush()
    kid = Child(family_id=family.id, name="Test Child", birth_year=2020)
    db.add(kid)
    db.flush()
    return kid
