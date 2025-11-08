from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from strings import get_string
from Tune.utils.database import get_chat_topics, get_lang


def TopicAccessCheck(mystic):
    """
    Decorator that checks if current topic is allowed for music commands.
    Only allows command execution if:
    1. Chat has topics assigned in database
    2. Current message_thread_id is in the allowed topics list
    """
    async def wrapper(client, message, *args, **kwargs):
        chat_id = message.chat.id
        
        # Get language for error messages
        try:
            language = await get_lang(chat_id)
            _ = get_string(language)
        except:
            _ = get_string("en")
        
        # Get all allowed topics for this chat
        allowed_topics = await get_chat_topics(chat_id)
        
        if not allowed_topics:
            return await mystic(client, message, *args, **kwargs)
        
        # Check if message is from a forum topic
        current_topic = message.message_thread_id
        if not current_topic:
            # Message is not from a topic (general chat)
            return await message.reply_text(
                _["topic_access_1"] 
            )
        
        # Check if current topic is in allowed list
        if current_topic not in allowed_topics:
            return await message.reply_text(
                _["topic_access_2"].format(current_topic)  # 
            )
        
        # Topic is allowed, proceed with the command
        return await mystic(client, message, *args, **kwargs)
    
    return wrapper
