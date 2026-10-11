"""进程内 builder 导入路径下 BM25 重排必须可用（2026-10-11 回归）。

主链 _build_local_search_engine（scripts/engines.py）用 _sys_path_tmp 临时
路径导入 search_v3。此前 bm25 走函数内惰性 `from bm25 import`：临时路径
在场时模块顶部的 SKILL_DIR 守卫不生效、路径撤除后惰性导入必然落空，
主链 local_search 全路径静默退化位次分（评测走干净路径测不到——评测与
生产不一致）。本测试在干净子进程里复刻生产的导入序列，锁死该契约。
"""
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_PROBE = textwrap.dedent("""
    import sys
    from pathlib import Path
    sys.path.insert(0, {scripts!r})
    from engines import _sys_path_tmp
    sub = str(Path({root!r}) / "sub-skills" / "local-search")
    with _sys_path_tmp(sub):
        import search_v3
    assert search_v3._bm25_rerank is not None, (
        "bm25 重排在进程内导入路径下不可用——函数内惰性导入回归？")
    print("OK")
""")


def test_inproc_import_keeps_bm25_rerank():
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE.format(scripts=str(ROOT / "scripts"),
                                             root=str(ROOT))],
        capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    assert proc.returncode == 0, (
        f"stdout={proc.stdout!r}\nstderr 尾部={proc.stderr[-800:]!r}")
    assert "OK" in proc.stdout
