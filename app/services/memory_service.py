from app.repositories import ChatRepository
from app.repositories.messages import MessageRepository
from app.db.models import Chat, Message
from typing import List, Optional
from fastapi import HTTPException
from datetime import datetime


class MemoryService:
    def __init__(
        self,
        chat_repository: ChatRepository,
        message_repository: MessageRepository = None,
    ):
        self.chat_repository = chat_repository
        self.message_repository = message_repository

    def get_chat_by_id(self, chat_id: int) -> Optional[Chat]:
        """
        Get a chat by ID.

        Args:
            chat_id: The ID of the chat

        Returns:
            Chat object or None if not found

        Raises:
            HTTPException: If database query fails
        """
        try:
            return self.chat_repository.get_by_id(chat_id)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to retrieve chat: {str(e)}"
            )

    def get_chats(self, user_id: str, feature_id: int) -> List[Chat]:
        """
        Get chats for a user filtered by feature_id.

        Args:
            user_id: The ID of the user
            feature_id: The feature ID to filter chats

        Returns:
            List of Chat objects

        Raises:
            HTTPException: If database query fails
        """
        try:
            return self.chat_repository.get_user_chats_by_feature(user_id, feature_id)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to retrieve chats: {str(e)}"
            )

    def get_chat_history(
        self,
        chat_id: int,
        count: int = 100,
    ) -> List[Message]:
        """
        Get message history for a chat.

        Args:
            chat_id: The ID of the chat

        Returns:
            List of Message objects

        Raises:
            HTTPException: If chat is not found or database query fails
        """
        try:
            chat = self.chat_repository.get_by_id(chat_id)
            if not chat:
                raise HTTPException(
                    status_code=404, detail=f"Chat with id {chat_id} not found"
                )
            return chat.messages
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to retrieve chat history: {str(e)}"
            )

    def save_message(self, chat_id: int, message: Message) -> Message:
        """
        Save a message to a chat.

        Args:
            chat_id: The ID of the chat
            message: The Message object to save

        Returns:
            The saved Message object

        Raises:
            HTTPException: If chat is not found, message is invalid, or save fails
        """
        if not message:
            raise HTTPException(status_code=400, detail="Message cannot be None")

        try:
            chat = self.chat_repository.get_by_id(chat_id)
            if not chat:
                raise HTTPException(
                    status_code=404, detail=f"Chat with id {chat_id} not found"
                )

            # Set chat_id on message if not already set
            if not message.chat_id:
                message.chat_id = chat_id

            # Use MessageRepository if available, otherwise use ChatRepository
            if self.message_repository:
                return self.message_repository.create(message)
            else:
                # Fallback: try to use chat_repository if it has save_message
                if hasattr(self.chat_repository, "save_message"):
                    return self.chat_repository.save_message(chat_id, message)
                else:
                    raise Exception("No method available to save message")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to save message: {str(e)}"
            )

    def delete_message(self, message_id: int) -> None:
        """
        Delete a message.

        Args:
            message_id: The ID of the message to delete

        Raises:
            HTTPException: If message is not found or deletion fails
        """
        try:
            if not self.message_repository:
                raise HTTPException(
                    status_code=500, detail="MessageRepository is not available"
                )

            message = self.message_repository.get_by_id(message_id)
            if not message:
                raise HTTPException(
                    status_code=404, detail=f"Message with id {message_id} not found"
                )

            self.message_repository.delete(message_id)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to delete message: {str(e)}"
            )

    def delete_chat(self, chat_id: int) -> None:
        """
        Delete a chat and all its messages.

        Args:
            chat_id: The ID of the chat to delete

        Raises:
            HTTPException: If chat is not found or deletion fails
        """
        try:
            chat = self.chat_repository.get_by_id(chat_id)
            if not chat:
                raise HTTPException(
                    status_code=404, detail=f"Chat with id {chat_id} not found"
                )

            # Delete the chat (messages will be cascade deleted if foreign key is set up)
            self.chat_repository.delete(chat_id)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to delete chat: {str(e)}"
            )

    def create_chat(self, user_id: str, feature_id: int, title: str) -> Chat:
        """
        Create a new chat.

        Args:
            user_id: The ID of the user creating the chat
            feature_id: The ID of the feature this chat belongs to
            title: The title of the chat

        Returns:
            The created Chat object

        Raises:
            HTTPException: If validation fails or creation fails
        """
        if not title or not title.strip():
            raise HTTPException(status_code=400, detail="Chat title cannot be empty")

        try:
            chat = Chat(
                user_id=user_id,
                feature_id=feature_id,
                title=title.strip(),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            return self.chat_repository.create(chat)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to create chat: {str(e)}"
            )

    def update_chat(self, chat_id: int, title: str) -> Chat:
        """
        Update a chat's title.

        Args:
            chat_id: The ID of the chat to update
            title: The new title for the chat

        Returns:
            The updated Chat object

        Raises:
            HTTPException: If chat is not found, validation fails, or update fails
        """
        if not title or not title.strip():
            raise HTTPException(status_code=400, detail="Chat title cannot be empty")

        try:
            chat = self.chat_repository.get_by_id(chat_id)
            if not chat:
                raise HTTPException(
                    status_code=404, detail=f"Chat with id {chat_id} not found"
                )

            chat.title = title.strip()
            chat.updated_at = datetime.now()
            return self.chat_repository.update(chat)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to update chat: {str(e)}"
            )
