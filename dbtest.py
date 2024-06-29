import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import BaseModel
from database.models.tasks import Task
from database.models.comments import Comment, CommentType
from database.models.documents import Document
from database.models.task_notifications import TaskNotification
from database.models.users import User
from database.models.organizations import Organization
from database.models.objects import Object
from database.models.statuses import Status
from database.models.task_types import TaskType

from shared.app_config import app_config
from database import db_manager, async_dbsession

async def async_main():
    await async_clean()
    async with db_manager.engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.create_all)

    async with async_dbsession() as session:
        async with session.begin():
            user1 = User(
                last_name="Doe",
                first_name="John",
                middle_name="",
                email="john.doe@example.com",
                phone_number="1234567890",
                telegram_nick="johndoe",
                telegram_id=12345,
                position="Developer",
                verificated=True,
                active=True,
                admin=False
            )
            session.add(user1)

            organization1 = Organization(
                name="Test Organization",
                description="This is a test organization",
                address="123 Test Street"
            )
            session.add(organization1)

            object1 = Object(
                name="Test Object",
                organization=organization1,
                description="This is a test object",
                address="123 Test Object Street",
                area_sq_meters=100.0,
                num_apartments=10
            )
            session.add(object1)

            task_type1 = TaskType(name="Test Task Type", active=True)
            session.add(task_type1)

            status1 = Status(name="Test Status", active=True)
            session.add(status1)

            task1 = Task(
                name="Test Task",
                task_type=task_type1,
                status=status1,
                object=object1,
                supplier=user1,
                supervisor=user1,
                executor=user1,
                description="This is a test task"
            )
            session.add(task1)

            document1 = Document(
                title="Test Document",
                type="pdf",
                author=user1
            )
            session.add(document1)

            comment1 = Comment(
                task=task1,
                user=user1,
                type=CommentType.comment,
                content="This is a test comment",
                metadata={"key": "value"}
            )
            session.add(comment1)

            notification1 = TaskNotification(
                task=task1,
                user=user1,
                telegram_message_id=123456,
                notification_type="status_update"
            )
            session.add(notification1)

            # Adding more test data
            user2 = User(
                last_name="Smith",
                first_name="Jane",
                middle_name="",
                email="jane.smith@example.com",
                phone_number="0987654321",
                telegram_nick="janesmith",
                telegram_id=54321,
                position="Manager",
                verificated=True,
                active=True,
                admin=True
            )
            session.add(user2)

            task2 = Task(
                name="Second Test Task",
                task_type=task_type1,
                status=status1,
                object=object1,
                supplier=user2,
                supervisor=user1,
                executor=user2,
                description="This is another test task"
            )
            session.add(task2)

            document2 = Document(
                title="Second Test Document",
                type="docx",
                author=user2
            )
            session.add(document2)

            comment2 = Comment(
                task=task2,
                user=user2,
                type=CommentType.comment,
                content="This is another test comment",
                metadata={"key": "value"}
            )
            session.add(comment2)

            notification2 = TaskNotification(
                task=task2,
                user=user2,
                telegram_message_id=654321,
                notification_type="status_update"
            )
            session.add(notification2)

        await session.commit()
        print("Тестовые данные добавлены успешно.")

async def async_clean():
    async with db_manager.engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.drop_all)

    print("База данных успешно очищена.")

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(async_main())
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()

if __name__ == "__main__":
    main()
