"""Generate MonitorQS.icns icon."""
import os, subprocess, tempfile


def make_icns(out_path: str):
    from PIL import Image, ImageDraw, ImageFont
    import io

    sizes = [16, 32, 64, 128, 256, 512, 1024]
    tmp = tempfile.mkdtemp()
    iconset = os.path.join(tmp, "MonitorQS.iconset")
    os.makedirs(iconset)

    for sz in sizes:
        img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        r = int(sz * 0.18)

        d.rounded_rectangle([0, 0, sz - 1, sz - 1], radius=r, fill=(28, 28, 30, 255))

        margin = int(sz * 0.15)
        bar_h = max(2, int(sz * 0.18))
        bar_y = int(sz * 0.22)
        n_bars = 5
        bar_w = (sz - 2 * margin) // n_bars
        for i in range(n_bars):
            gray = int(i * 200 / (n_bars - 1))
            x = margin + i * bar_w
            d.rectangle([x, bar_y, x + bar_w - 1, bar_y + bar_h], fill=(gray, gray, gray, 255))

        try:
            fnt_sz = max(8, int(sz * 0.28))
            fnt = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", fnt_sz)
        except Exception:
            fnt = ImageFont.load_default()

        text = "QS"
        bbox = d.textbbox((0, 0), text, font=fnt)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        text_y = bar_y + bar_h + int(sz * 0.08)
        d.text(
            ((sz - tw) / 2 - bbox[0], text_y - bbox[1]),
            text, fill=(0, 122, 255, 255), font=fnt,
        )

        buf = io.BytesIO()
        img.save(buf, "PNG")
        png_data = buf.getvalue()

        fname = f"icon_{sz}x{sz}.png"
        with open(os.path.join(iconset, fname), "wb") as f:
            f.write(png_data)
        if sz <= 512:
            with open(os.path.join(iconset, f"icon_{sz}x{sz}@2x.png"), "wb") as f:
                f.write(png_data)

    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", out_path], check=True)
    print(f"Icon saved: {out_path}")


if __name__ == "__main__":
    make_icns("MonitorQS.icns")
