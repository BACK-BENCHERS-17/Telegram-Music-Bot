import asyncio
import os
import time
import aiofiles
from typing import Optional, Union
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Voice
from pyrogram.errors import FloodWait, MessageNotModified
import config
from Tune import app
from Tune.utils.formatters import (
    check_duration,
    convert_bytes,
    get_readable_time,
    seconds_to_min,
)

class TeleAPI:
    def __init__(self):
        self.chars_limit = 4096
        self.sleep = 5
        # Optimized chunk sizes for different file types
        self.chunk_sizes = {
            'small': 1024 * 512,    # 512KB for files < 50MB
            'medium': 1024 * 1024,   # 1MB for files 50MB-200MB  
            'large': 1024 * 2048,    # 2MB for files > 200MB
        }
        # Progress update thresholds (reduced for smoother updates)
        self.progress_thresholds = [1, 5, 10, 25, 50, 75, 90, 95, 99]
        
    def _get_optimal_chunk_size(self, file_size: int) -> int:
        """Get optimal chunk size based on file size for faster downloads"""
        if file_size < 50 * 1024 * 1024:  # < 50MB
            return self.chunk_sizes['small']
        elif file_size < 200 * 1024 * 1024:  # < 200MB
            return self.chunk_sizes['medium']
        else:  # > 200MB
            return self.chunk_sizes['large']
    
    async def send_split_text(self, message, string: str) -> bool:
        n = self.chars_limit
        out = [string[i : i + n] for i in range(0, len(string), n)]
        for j, x in enumerate(out[:3], 1):
            try:
                await message.reply_text(x, disable_web_page_preview=True)
                if j < len(out[:3]):  # Don't sleep after last message
                    await asyncio.sleep(0.5)  # Reduced sleep time
            except FloodWait as e:
                await asyncio.sleep(e.x)
                await message.reply_text(x, disable_web_page_preview=True)
            except Exception:
                continue
        return True

    async def get_link(self, message):
        return message.link

    async def get_filename(self, file, audio: Union[bool, str] = None) -> str:
        try:
            file_name = getattr(file, "file_name", None)
            if not file_name:
                file_name = "ᴛᴇʟᴇɢʀᴀᴍ ᴀᴜᴅɪᴏ" if audio else "ᴛᴇʟᴇɢʀᴀᴍ ᴠɪᴅᴇᴏ"
        except Exception:
            file_name = "ᴛᴇʟᴇɢʀᴀᴍ ᴀᴜᴅɪᴏ" if audio else "ᴛᴇʟᴇɢʀᴀᴍ ᴠɪᴅᴇᴏ"
        return file_name

    async def get_duration(self, file_obj, file_path: Optional[str] = None) -> str:
        try:
            if hasattr(file_obj, "duration") and file_obj.duration:
                return seconds_to_min(file_obj.duration)
        except Exception:
            pass
        if file_path:
            try:
                # Use asyncio for non-blocking duration check
                dur = await asyncio.get_event_loop().run_in_executor(
                    None, check_duration, file_path
                )
                return seconds_to_min(dur)
            except Exception:
                pass
        return "Unknown"

    async def get_filepath(
        self,
        audio: Union[bool, str] = None,
        video: Union[bool, str] = None,
    ) -> str:
        base = os.path.realpath("downloads")
        # Ensure downloads directory exists
        os.makedirs(base, exist_ok=True)
        
        if audio:
            try:
                ext = (audio.file_name.split(".")[-1]) if not isinstance(audio, Voice) else "ogg"
            except Exception:
                ext = "ogg"
            file_name = f"{audio.file_unique_id}.{ext}"
            return os.path.join(base, file_name)
        if video:
            try:
                ext = video.file_name.split(".")[-1]
            except Exception:
                ext = "mp4"
            file_name = f"{video.file_unique_id}.{ext}"
            return os.path.join(base, file_name)
        return os.path.join(base, f"{int(time.time())}.dat")

    async def _get_media_info(self, message) -> tuple:
        """Extract media information for better quality selection"""
        media = message.reply_to_message
        if not media:
            return None, 0, ""
        
        # Check different media types for best quality
        file_obj = None
        file_size = 0
        media_type = ""
        
        if media.video:
            file_obj = media.video
            file_size = media.video.file_size or 0
            media_type = "video"
            # Prefer higher resolution videos
            if hasattr(media.video, 'width') and hasattr(media.video, 'height'):
                resolution = media.video.width * media.video.height
                # Log resolution for debugging
                print(f"Video resolution: {media.video.width}x{media.video.height} ({resolution} pixels)")
        elif media.animation:
            file_obj = media.animation
            file_size = media.animation.file_size or 0
            media_type = "animation"
        elif media.document:
            file_obj = media.document
            file_size = media.document.file_size or 0
            media_type = "document"
            # Check if document is actually a video
            if media.document.mime_type and media.document.mime_type.startswith('video/'):
                media_type = "video_document"
        elif media.audio:
            file_obj = media.audio
            file_size = media.audio.file_size or 0
            media_type = "audio"
        elif media.voice:
            file_obj = media.voice
            file_size = media.voice.file_size or 0
            media_type = "voice"
            
        return file_obj, file_size, media_type

    async def download(self, _, message, mystic, fname: str) -> bool:
        # Optimized progress tracking
        progress_tracker = {}
        last_update_time = 0
        update_interval = 2.0  # Update every 2 seconds max
        
        if os.path.exists(fname):
            return True

        # Get media info for optimization
        file_obj, file_size, media_type = await self._get_media_info(message)
        if not file_obj:
            await mystic.edit_text("❌ No media found to download")
            return False

        async def down_load():
            async def progress(current, total):
                nonlocal last_update_time
                current_time = time.time()
                
                if current == total or total == 0:
                    return
                    
                # Throttle updates for better performance
                if current_time - last_update_time < update_interval and current != total:
                    return
                    
                last_update_time = current_time

                if message.id not in progress_tracker:
                    progress_tracker[message.id] = {
                        'start_time': current_time,
                        'last_current': 0,
                        'speeds': []
                    }

                tracker = progress_tracker[message.id]
                elapsed = max(current_time - tracker['start_time'], 1e-3)
                
                # Calculate instantaneous speed for more accurate ETA
                time_diff = max(current_time - (tracker.get('last_time', tracker['start_time'])), 1e-3)
                current_diff = current - tracker['last_current']
                instant_speed = current_diff / time_diff
                
                # Keep running average of speeds for stability
                tracker['speeds'].append(instant_speed)
                if len(tracker['speeds']) > 10:  # Keep last 10 speed measurements
                    tracker['speeds'] = tracker['speeds'][-10:]
                
                avg_speed = sum(tracker['speeds']) / len(tracker['speeds'])
                tracker['last_current'] = current
                tracker['last_time'] = current_time

                upl = InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="ᴄᴀɴᴄᴇʟ", callback_data="stop_downloading")]]
                )
                
                percentage = (current * 100) / total
                
                try:
                    eta_s = int((total - current) / max(avg_speed, 1e-6)) if avg_speed > 0 else 0
                except Exception:
                    eta_s = 0

                eta = get_readable_time(eta_s) or "0 sᴇᴄᴏɴᴅs"
                total_size = convert_bytes(total)
                completed_size = convert_bytes(current)
                speed_h = convert_bytes(avg_speed)
                percentage_i = int(percentage)
                
                # More frequent updates for better user experience
                should_update = any(
                    threshold - 1 < percentage_i <= threshold 
                    for threshold in self.progress_thresholds
                )
                
                if should_update or current == total:
                    try:
                        # Enhanced progress message with media type info
                        progress_text = _["tg_1"].format(
                            app.mention, total_size, completed_size, 
                            str(percentage)[:5], speed_h, eta
                        )
                        
                        # Add media type and quality info
                        if media_type == "video" and hasattr(file_obj, 'width'):
                            progress_text += f"\n📺 Quality: {file_obj.width}x{file_obj.height}"
                        elif media_type in ["audio", "voice"]:
                            progress_text += f"\n🎵 Audio Quality: {getattr(file_obj, 'title', 'Unknown')}"
                            
                        await mystic.edit_text(
                            text=progress_text,
                            reply_markup=upl,
                        )
                        # Mark this threshold as used
                        if percentage_i in self.progress_thresholds:
                            self.progress_thresholds.remove(percentage_i)
                            
                    except (MessageNotModified, FloodWait) as e:
                        if isinstance(e, FloodWait):
                            await asyncio.sleep(min(e.x, 5))  # Cap flood wait at 5 seconds
                    except Exception:
                        pass

            progress_tracker[message.id] = {'start_time': time.time(), 'last_current': 0, 'speeds': []}
            
            try:
                # Enhanced download with better error handling and retries
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        # Use optimal chunk size based on file size
                        chunk_size = self._get_optimal_chunk_size(file_size)
                        
                        # Create download task with timeout
                        download_task = asyncio.create_task(
                            app.download_media(
                                message.reply_to_message,
                                file_name=fname,
                                progress=progress,
                                # These parameters might not be available in all pyrogram versions
                                # Remove if causing errors
                            )
                        )
                        
                        # Set timeout based on file size (5 minutes + 1 minute per 100MB)
                        timeout = 300 + (file_size / (100 * 1024 * 1024)) * 60
                        
                        await asyncio.wait_for(download_task, timeout=timeout)
                        break  # Success, exit retry loop
                        
                    except asyncio.TimeoutError:
                        if attempt < max_retries - 1:
                            await mystic.edit_text(f"⏱️ Download timeout. Retrying... ({attempt + 1}/{max_retries})")
                            await asyncio.sleep(2)
                            continue
                        else:
                            await mystic.edit_text("❌ Download timeout. File too large or connection too slow.")
                            return False
                            
                    except FloodWait as e:
                        await asyncio.sleep(e.x)
                        if attempt < max_retries - 1:
                            continue
                        else:
                            await mystic.edit_text("❌ Rate limited. Please try again later.")
                            return False
                            
                    except Exception as e:
                        if attempt < max_retries - 1:
                            await mystic.edit_text(f"⚠️ Download error. Retrying... ({attempt + 1}/{max_retries})")
                            await asyncio.sleep(2)
                            continue
                        else:
                            await mystic.edit_text(f"❌ Download failed: {str(e)[:100]}")
                            return False

                try:
                    elapsed_time = time.time() - progress_tracker[message.id]['start_time']
                    elapsed = get_readable_time(int(elapsed_time))
                    
                    # Verify file was actually downloaded and has content
                    if os.path.exists(fname) and os.path.getsize(fname) > 0:
                        file_size_mb = os.path.getsize(fname) / (1024 * 1024)
                        await mystic.edit_text(
                            _["tg_2"].format(elapsed) + f"\n📁 Size: {file_size_mb:.1f} MB"
                        )
                    else:
                        await mystic.edit_text("❌ Download completed but file is empty or corrupted.")
                        return False
                        
                except Exception:
                    elapsed = "Unknown"
                    await mystic.edit_text(_["tg_2"].format(elapsed))
                    
            except Exception as e:
                await mystic.edit_text(_["tg_3"] + f"\nError: {str(e)[:100]}")
                return False
            finally:
                # Cleanup progress tracker
                progress_tracker.pop(message.id, None)

        # Create download task with proper error handling
        try:
            task = asyncio.create_task(down_load())
            config.lyrical[mystic.id] = task
            await task
            
            # Verify task completed successfully
            verify = config.lyrical.get(mystic.id)
            if not verify:
                return False
                
            # Verify file exists and has content
            if not os.path.exists(fname) or os.path.getsize(fname) == 0:
                await mystic.edit_text("❌ Download failed - file not found or empty")
                return False
                
            return True
            
        except asyncio.CancelledError:
            await mystic.edit_text("🛑 Download cancelled")
            return False
        except Exception as e:
            await mystic.edit_text(f"❌ Unexpected error: {str(e)[:100]}")
            return False
        finally:
            config.lyrical.pop(mystic.id, None)
            # Reset progress thresholds for next download
            self.progress_thresholds = [1, 5, 10, 25, 50, 75, 90, 95, 99]
