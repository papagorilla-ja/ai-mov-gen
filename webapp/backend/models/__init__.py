"""
SQLAlchemy モデル定義。
core.database.init_db() がこのパッケージをインポートすることで
Base.metadata にテーブル定義が登録される。
"""
from models.project import Project          # noqa: F401
from models.video import Video              # noqa: F401
from models.scenario import Scenario        # noqa: F401
from models.scene import Scene              # noqa: F401
from models.scene_asset import SceneAsset  # noqa: F401
from models.speaker import Speaker          # noqa: F401
from models.voice_recording import VoiceRecording  # noqa: F401
from models.video_style import VideoStyle   # noqa: F401
from models.style_template import StyleTemplate  # noqa: F401
from models.generation_history import GenerationHistory  # noqa: F401
from models.scene_tts_cache import SceneTtsCache  # noqa: F401
