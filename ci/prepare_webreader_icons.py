#!/usr/bin/env python3
"""Offline iOS 12 icon generator from approved WebReader art.

Produces opaque RGB PNGs for the Xcode AppIcon asset catalog using only
Python 3 stdlib + macOS sips. No external downloads, fonts or SVG renderer.
"""
import base64
from pathlib import Path
import struct
import subprocess
import tempfile
import zlib

ROOT = Path(__file__).resolve().parent.parent
ICON_DIR = ROOT / "MangaReader12/Assets.xcassets/AppIcon.appiconset"
# Original approved red 画 on black, sampled at 256 pixels. 4-bit red
# samples, high nibble first; all pixels are opaque (iOS rounds the corners).
MASK = """eNrtnM9vFkUYx7v9C97dxAun7gwUApx2FtSAl+7LxWiNra8XFbSBcqPRpnBsIkIxHkg0qPVCIgdFExsh0QAHDkRFQuQCB01KL3ghtO/F/oC27zq/d/btvuXtzGxff8z30nfeNvvZ59mZZ56ZfaZdXU5OTk5OTk5OTk5OTk5OTk5OTk5OTk5OTk5OTk5Plef7fif5AQCg0lH8aAdvwANwx0oEQOfMj86mNyAIO4WHO9J0JYk64wAfEPPT+l0EejqDh9tTrFXsgEpHRl40TvipmQM8HdsJnZtPHRAa2QFCAPwC0d8BH4TsA/noi48AomiE8ev3kPYDkJfboCBCqDdNTR3gAYQi1BYxEh8QV3JM8NO7uiFA13xyF3vrkr+i+wD2XZ2cODF8pFarHahWqzWh14eljp5gmjjD9OEk1hffYH2XZrqhNwK8LeICjTmsVFsrkR4fzhhAVV3S6gBeOG4Hnz7W44Pdlvj1t/X4vZb46fda/R9E1zvKD8Chtq5Ohsf09PRtqmvXrl7F429y8nM8HsnYHB6u1fRmoG64s0EBs7evkWteZBedINckOjLFuxeODkiNk74f+gGbJcjsEOpmwWArZt+aOJzIKwchuabvsynmPOMvxWjdKB1qzz/hR6eTqGWMTTJ+7o+aJkr99MMjc2+hRewGBJ+aH4rZ12K64wmDKn42t1N34t9A6X+IzfdlumA1iQ+y3sNvIJQtlR92lcJXMzAv515P5fNvA6Pe1ubDCLP1hcJXPFRWvi06QKWAHxbcoH0+H+bsBsAafjfukwCVlu+DKskrxRNu6n8V2lchOoCikhzggf4fI34DPh1/fPw3HpPwQ2MiQr+NopLW3N1gV/rHYXwDkcyypxQ++2YfdgYqxwEe7G2kK6cSxHsBlPHvMb8niOI7aXpBOMAk8hby0QyG/SJuIBf/EUv995FsMyENFi59q/6PqL8fHuZLjDjjJ+wLRPOVe8psZDEYdQN0lqXT52KKq0o+qrIvXmT9YYj7B1m4AU9OoHj483SocZuLr3FWRXuGtRdxF4R0EYiMp0PmRZ9+Qi+0me6dxB3y24tjCRssFSOnKzM+7V7t6AkG474ye2UsMhyN8jnSJ/p8u/nu5TgZJw+ncWvMyAHezovH8XDid4Cea5e/OpiIvnKzz2BCDHaTBPR0Qu8AomfbxDcw/6BcfZ7UjwJge4O48dFng3RjYW+79v8UV1/OnPFBRXvK2cav8egUmXr2iP7FVvsTfHm0zFf/5wVxuZoo/PqCPj+W2xg38Wjaw1sLNMLl80/cPfpl96uieH/mjXf1+eiOvMrDQcmfZwEwmcriP2mOCPfgW42zsboE9PnRlOxT6WjG5/ONtJ81RZe7nOe/Hxnw5TMlUTWWfJDzP3sckn8y4VMhm52h9g409v+4GlSl/ZBtuin5L2kK/miO/2Vkwh+RZsQKn+525vikKVbro0jlD+rvv6r8T8hDzfg9ysNZYk1wsIjfSIz4wqZl0scVfoUAM36FTBWt+D0GfHHNxTw/pHNTjh8ofNwZd1nhyz61sB4/ADQ/EfHnvTzfYP5R+Ghd+5v5wA4/8+lavpfn46bkRwp/tRQ+fuBBxoe42Z31P8KHCr9SAp8k+Or6k6T74m+HyuGDHJ9E/BbxrxQ+RGviP2qaf8vkz2OGwi+Y/2ALPrLEx9eM60pnUNZ/vGmfDxT/K/x5lo5m/Y9MwKiE5w+K7V88epxuAPP878lRth98ttTnr/Cfov8OH2jzkaX+11/U//6HfOr/rf8QfmP2/uz03PScbE5PT8/dn5vZrPizQPZ7Ern/hFNjnB3F1TLjX67/z9MJR41/ufWPTf8X8+mCZ83669Cm8YvWP3AT7V+b//hN+UfZ/Iq6/oEsHewv5Ef2+X/R/DvI8t+Q7tSVwT9UzO+he4MqX5mrSvP/VsmnrwBDuf7pya0/NoHfledXqDv6N6v/NfEXN4G/oM1PyrCfAvP+90rg5/P/Zj44q26wlW1/1Dz+lPHfsznjb73447VafyL79hft/wSghf224l+Ujf95Vu3QtP+GDhbuP0T240/x/iOybr+3bv7RtP8Ny+dvza+/o1z9Sav8x6L/t9WVzbhs/f04Zq9Dj5Vt/7bMfiIl/yTvqDL/ozy/yzZ/+RoTT/hXePNO0f6fJfvp/LNnk9c/zfbvSTXW38jE/5ENvkH/1+fvtsM/9K/nR/b5y5NMZyZzmmrB77LFF+9/50VVPll3iRJBKP92CNizf0Tl98oGKii5F6/c03fs8cGIYjIUb6MfQFkEqdZjCv6ANX5QzP+Yl5V4XR7+UfFocSQU/CVQMn+poKyGlKOx/HflVcrfbyH+4auOK3xej708UFTSgdOxV+hr8iHQzDd5/uNK/2P8XwcKSwwDmivOftWHf+upfLP1R47/TLp661TUoqYIgDcvHqeVyhXMR1b49AyVnH8BHB6MABl6xfdKRwHh+yq/zw5fFN3RVz1Ff0uqL+kfhXQwWOKfT9WSj3wFaJH9MhzttxP/zivv39atKPfzwSh+Sbx/7TPJf2T9x0JBjXnFJ6HHB6zKPm++rL9pmPU/wV+s0lo2hFBb569iW/zr6vt3ANviQ5Tnm7z/l/xa7bVqs5KEf4ibfnGgVnvLiv2y/ogegdqI6lbqD+CM6dEXM/9b4A+a1H+0+canNP62tLN8CyewBkz42835JvaTI9SG4w/brx//4U5ZfVerFgjJSJR9F9P4c+SYBX63XMXyLZ+2z9/GVVmMOQAM+LLi+gFC0QaOv2YvI434cku5fimideD5c11sEhZN5Vy0Ugxiws/Sf/KPDNo9RkfPocjNqLRPP/8PxA57emEjx3o8ZTOysWp0/JynHz9v7FSRp2yG/mmS/vPp54eNHmoK5MbNEwPzu4Jecv5y9dyGTzF4YjG4PGRy/KB7C36AVwY1DrLwl6G/9xmdPvB2Xj09GOmc4aAj59Gnhqcv2P9x0DrGA974eqzP+ASQp32GJwA+gOZn8Txg9M8LzM8/eb7Bs+vgP79xcnJycnJycnJycnJycnJycnJycnJycnJycnLqgP4GKN+DmA=="""

def chunk(tag: bytes, data: bytes) -> bytes:
    payload = tag + data
    return (struct.pack(">I", len(data)) + payload +
            struct.pack(">I", zlib.crc32(payload) & 0xffffffff))

def source_png() -> bytes:
    packed = zlib.decompress(base64.b64decode(MASK))
    if len(packed) != 256 * 256 // 2:
        raise ValueError("WebReader icon source is corrupt")
    pixels = bytearray()
    for y in range(256):
        pixels.append(0)
        for pair in packed[y * 128 : (y + 1) * 128]:
            pixels.extend(((pair >> 4) * 17, 0, 0,
                           (pair & 0x0f) * 17, 0, 0))
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 256, 256, 8, 2, 0, 0, 0)
    return (signature + chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", zlib.compress(pixels, 9)) +
            chunk(b"IEND", b""))

def main() -> None:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="webreader-icon-") as tmp:
        master = Path(tmp) / "source.png"
        master.write_bytes(source_png())
        # Unique pixel sizes required by iPhone/iPad (iOS 12) and marketing.
        for pixels in (20, 29, 40, 58, 60, 76, 80, 87, 120, 152, 167, 180, 1024):
            target = ICON_DIR / ("icon-%d.png" % pixels)
            subprocess.run(
                ["sips", "-z", str(pixels), str(pixels),
                 str(master), "--out", str(target)],
                check=True, stdout=subprocess.DEVNULL,
            )
            data = target.read_bytes()
            if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
                raise ValueError("Invalid PNG from sips: " + str(target))
            if struct.unpack(">II", data[16:24]) != (pixels, pixels):
                raise ValueError("Unexpected dimensions: " + str(target))
    print("PASS: generated approved WebReader iOS12 AppIcon PNGs")

if __name__ == "__main__":
    main()
