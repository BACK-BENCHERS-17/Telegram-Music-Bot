import asyncio
from pyrogram import filters
from pyrogram.types import Message

import config
from config import BANNED_USERS
from strings import get_string
from Tune import app
from Tune.utils.database import (
    get_chat_topics,
    set_chat_topic,
    unset_chat_topic,
    is_topic_in_chat,
    get_lang,
)
from Tune.utils.decorators.admins import AdminRightsCheck
from Tune.utils.decorators.language import LanguageStart


@app.on_message(
    filters.command(["setmusictopic", "addmusictopic"]) & filters.group & ~BANNED_USERS
)
@AdminRightsCheck(require_active_chat=False)
async def set_music_topic_command(client, message: Message, _, chat_id):
    # Get language manually since LanguageStart isn't compatible
    try:
        language = await get_lang(message.chat.id)
        _ = get_string(language)
    except:
        _ = get_string("en")
    
    # Get topic ID from the message (forum topic)
    if not message.message_thread_id:
        return await message.reply_text(_["settopic_1"])  # "This command can only be used in forum topics."
    
    topic_id = message.message_thread_id
    
    # Check if topic already exists
    if await is_topic_in_chat(chat_id, topic_id):
        return await message.reply_text(_["settopic_2"].format(topic_id))  # "Topic ID {0} is already enabled for music"
    
    # Add topic
    success = await set_chat_topic(chat_id, topic_id)
    
    if success:
        await message.reply_text(_["settopic_3"].format(topic_id))  # "✅ Successfully enabled music for this topic"
    else:
        await message.reply_text(_["settopic_4"])  # "❌ Failed to enable music for this topic"


@app.on_message(
    filters.command(["unsetmusictopic", "removemusictopic"]) & filters.group & ~BANNED_USERS
)
@AdminRightsCheck(require_active_chat=False)
async def unset_music_topic_command(client, message: Message, _, chat_id):
    # Get language manually since LanguageStart isn't compatible
    try:
        language = await get_lang(message.chat.id)
        _ = get_string(language)
    except:
        _ = get_string("en")
    
    # Get topic ID from the message (forum topic)
    if not message.message_thread_id:
        return await message.reply_text(_["unsettopic_1"])  # "This command can only be used in forum topics."
    
    topic_id = message.message_thread_id
    
    # Check if topic exists
    if not await is_topic_in_chat(chat_id, topic_id):
        return await message.reply_text(_["unsettopic_2"].format(topic_id))  # "Topic ID {0} is not enabled for music"
    
    # Remove topic
    success = await unset_chat_topic(chat_id, topic_id)
    
    if success:
        await message.reply_text(_["unsettopic_3"].format(topic_id))  # "✅ Successfully disabled music for this topic"
    else:
        await message.reply_text(_["unsettopic_4"])  # "❌ Failed to disable music for this topic"


@app.on_message(
    filters.command(["musictopics", "listmusictopics"]) & filters.group & ~BANNED_USERS
)
@LanguageStart
async def list_music_topics_command(client, message: Message, _):
    chat_id = message.chat.id
    topics = await get_chat_topics(chat_id)
    
    if not topics:
        return await message.reply_text(_["listtopics_1"])  # "📋 No music topics are set for this chat."
    
    topics_text = "\n".join([f"• <code>{topic_id}</code>" for topic_id in topics])
    
    await message.reply_text(
        _["listtopics_2"].format(len(topics), topics_text)  # "📋 **Music Topics for this chat:**\n\nTotal: {0}\n\n{1}"
    )


# Additional command for admins to clear all topics
@app.on_message(
    filters.command(["clearmusictopics"]) & filters.group & ~BANNED_USERS
)
@LanguageStart
@AdminRightsCheck(require_active_chat=False)
async def clear_music_topics_command(client, message: Message, _, chat_id):
    topics = await get_chat_topics(chat_id)
    
    if not topics:
        return await message.reply_text(_["cleartopics_1"])  # "📋 No music topics are set for this chat."
    
    # Clear all topics
    from Tune.utils.database import clear_chat_topics
    success = await clear_chat_topics(chat_id)
    
    if success:
        await message.reply_text(_["cleartopics_2"].format(len(topics)))  # "✅ Successfully cleared all {0} music topics from this chat."
    else:
        await message.reply_text(_["cleartopics_3"])  # "❌ Failed to clear topics. Please try again."