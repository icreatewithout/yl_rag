import sys
import threading

import uvicorn

from yl_rag.settings import settings

# 兼容性补丁：给 Thread 对象手动挂载旧名称
if not hasattr(threading.Thread, "isAlive"):
    threading.Thread.isAlive = threading.Thread.is_alive


def main() -> None:
    """Entrypoint of the application."""
    if settings.reload and sys.platform.startswith("win"):
        uvicorn.run(
            "yl_rag.web.application:get_app",
            workers=settings.workers_count,
            host=settings.host,
            port=settings.port,
            reload=settings.reload,
            factory=True,
        )
    else:
        from yl_rag.gunicorn_runner import GunicornApplication

        # We choose gunicorn only if reload
        # option is not used, because reload
        # feature doesn't work with gunicorn workers.
        GunicornApplication(
            "yl_rag.web.application:get_app",
            host=settings.host,
            port=settings.port,
            workers=settings.workers_count,
            factory=True,
            accesslog="-",
            loglevel=settings.log_level.value.lower(),
            access_log_format='%r "-" %s "-" %Tf',
        ).run()


if __name__ == "__main__":
    main()
