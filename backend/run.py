"""启动脚本"""

import uvicorn
from app.core.config import get_settings


if __name__ == "__main__":
    settings = get_settings()

    uvicorn.run(
        "app.api.agent_app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        timeout_keep_alive=300
    )
