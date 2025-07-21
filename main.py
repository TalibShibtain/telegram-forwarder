import os
import subprocess
import asyncio
import logging
from telethon import TelegramClient, events
from telegram import Bot

# Decrypt encrypted session file before anything
decrypt_cmd = [
    "openssl", "enc", "-aes-256-cbc", "-d",
    "-in", "forwarder.enc",
    "-out", "forwarder_session.session",
    "-k", os.environ['SESSION_PASS']
]
subprocess.run(decrypt_cmd, check=True)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TelegramForwarder:
    def __init__(self):
        self.api_id = int(os.environ['API_ID'])
        self.api_hash = os.environ['API_HASH']
        self.bot_token = os.environ['BOT_TOKEN']
        self.source_channel = os.environ['SOURCE_CHANNEL']
        self.target_chat = os.environ['TARGET_CHAT']

        self.client = TelegramClient('forwarder_session', self.api_id, self.api_hash)
        self.bot = Bot(token=self.bot_token)
        self.message_count = 0

        logger.info("Telegram Forwarder initialized")

    async def forward_message(self, event):
        """Forward message from source to target"""
        try:
            message = event.message
            self.message_count += 1
            
            # Handle text messages
            if message.text:
                await self.bot.send_message(
                    chat_id=self.target_chat,
                    text=message.text,
                    parse_mode='HTML' if message.entities else None
                )
                logger.info(f"✅ Text message #{self.message_count} forwarded")
                
            # Handle photos
            elif message.photo:
                photo_bytes = await self.client.download_media(message.photo, bytes)
                await self.bot.send_photo(
                    chat_id=self.target_chat,
                    photo=photo_bytes,
                    caption=message.text or ""
                )
                logger.info(f"✅ Photo #{self.message_count} forwarded")
                
            # Handle documents
            elif message.document:
                doc_bytes = await self.client.download_media(message.document, bytes)
                await self.bot.send_document(
                    chat_id=self.target_chat,
                    document=doc_bytes,
                    caption=message.text or ""
                )
                logger.info(f"✅ Document #{self.message_count} forwarded")
                
            # Handle videos
            elif message.video:
                video_bytes = await self.client.download_media(message.video, bytes)
                await self.bot.send_video(
                    chat_id=self.target_chat,
                    video=video_bytes,
                    caption=message.text or ""
                )
                logger.info(f"✅ Video #{self.message_count} forwarded")
                
            # Handle stickers
            elif message.sticker:
                sticker_bytes = await self.client.download_media(message.sticker, bytes)
                await self.bot.send_sticker(
                    chat_id=self.target_chat,
                    sticker=sticker_bytes
                )
                logger.info(f"✅ Sticker #{self.message_count} forwarded")
                
        except TelegramError as e:
            logger.error(f"❌ Telegram error: {e}")
        except Exception as e:
            logger.error(f"❌ Error forwarding message: {e}")
    
    async def start(self):
        """Start the forwarder bot"""
        try:
            # Start the client
            await self.client.start()
            logger.info("✅ Telegram client connected successfully!")
            
            # Test bot connection
            test_msg = await self.bot.send_message(
                self.target_chat, 
                f"🚀 Forwarder Bot Started!\n\n📡 Listening to: {self.source_channel}\n📤 Forwarding to: {self.target_chat}\n\n✅ Ready to forward messages!"
            )
            logger.info("✅ Bot connection tested successfully!")
            
            # Set up message handler
            @self.client.on(events.NewMessage(chats=self.source_channel))
            async def handle_new_message(event):
                logger.info(f"📨 New message from {self.source_channel}")
                await self.forward_message(event)
            
            logger.info(f"👂 Now listening for messages from: {self.source_channel}")
            logger.info("🔄 Bot is running continuously...")
            
            # Send periodic status updates (every 6 hours)
            async def status_update():
                while True:
                    await asyncio.sleep(21600)  # 6 hours
                    try:
                        await self.bot.send_message(
                            self.target_chat,
                            f"💚 Bot Status: Running\n📊 Messages forwarded today: {self.message_count}\n🕐 Last check: {time.strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                        logger.info("📊 Status update sent")
                    except Exception as e:
                        logger.error(f"Status update failed: {e}")
            
            # Run status updates in background
            asyncio.create_task(status_update())
            
            # Keep the bot running
            await self.client.run_until_disconnected()
            
        except Exception as e:
            logger.error(f"❌ Error starting bot: {e}")
            raise

async def main():
    """Main function with error handling and restart logic"""
    restart_count = 0
    max_restarts = 10
    
    while restart_count < max_restarts:
        try:
            logger.info(f"🚀 Starting Telegram Forwarder (attempt {restart_count + 1})")
            
            # Check environment variables
            required_vars = ['API_ID', 'API_HASH', 'BOT_TOKEN', 'SOURCE_CHANNEL', 'TARGET_CHAT']
            missing = [var for var in required_vars if not os.environ.get(var)]
            
            if missing:
                logger.error(f"❌ Missing environment variables: {', '.join(missing)}")
                logger.error("Please set these in your Render dashboard!")
                return
            
            # Create and start forwarder
            forwarder = TelegramForwarder()
            await forwarder.start()
            
            # If we reach here, it was a clean shutdown
            logger.info("✅ Bot stopped cleanly")
            break
            
        except Exception as e:
            restart_count += 1
            logger.error(f"💥 Bot crashed (attempt {restart_count}): {e}")
            
            if restart_count < max_restarts:
                sleep_time = min(300, 30 * restart_count)  # Progressive backoff, max 5 minutes
                logger.info(f"🔄 Restarting in {sleep_time} seconds...")
                await asyncio.sleep(sleep_time)
            else:
                logger.error("❌ Max restart attempts reached. Exiting.")
                break

if __name__ == "__main__":
    # Run the bot
    asyncio.run(main())
