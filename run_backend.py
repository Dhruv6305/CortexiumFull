import os
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "timeout;3000000|stimeout;3000000|rtsp_transport;tcp"

import uvicorn
import asyncio
import sys
from dotenv import load_dotenv

load_dotenv()

# Fix for Windows asyncio loop issues with Uvicorn/WatchFiles on Python 3.12
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if __name__ == "__main__":
    print("[Backend] Starting Cortexium 2.0 Backend...")
    
    # Force SelectorEventLoop for stability on Windows with strict firewalls
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        loop_name = "asyncio"
    else:
        loop_name = "auto"

    uvicorn.run(
        "backend.main:app", 
        host="0.0.0.0", 
        port=4040, 
        log_level="info",
        reload=False,
        loop=loop_name
    )
