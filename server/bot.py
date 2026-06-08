"""
bot.py — OtoScope Telegram Bot

Kullanıcı ilan metni veya Sahibinden/Arabam.com linki gönderir,
bot analiz edip sonucu döner.

Kurulum:
  pip install python-telegram-bot
  server/.env dosyasına TELEGRAM_BOT_TOKEN ekle

Çalıştırma:
  python bot.py
"""

import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv(Path(__file__).parent / ".env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = os.getenv("BOT_API_URL", "http://127.0.0.1:8000")

_VERDICT_EMOJI = {"DEAL": "✅", "FAIR": "🟡", "OVERPRICED": "❌"}
_VERDICT_TR = {"DEAL": "ALIM FIRSATI", "FAIR": "PİYASA FİYATI", "OVERPRICED": "PAHALI"}


def _fmt_price(p: int | None) -> str:
    if p is None:
        return "—"
    return f"₺{p:,}".replace(",", ".")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 *OtoScope Bot*'a hoş geldiniz\\!\n\n"
        "İlan metnini veya Sahibinden/Arabam\\.com linkini gönderin, analiz edeyim\\.\n\n"
        "Komutlar:\n"
        "/yardim — bu mesaj\n"
        "/plaka 34ABC123 — plaka şehri sorgula",
        parse_mode="MarkdownV2",
    )


async def cmd_yardim(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


async def cmd_plaka(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args:
        await update.message.reply_text("Kullanım: /plaka 34ABC123")
        return
    plate = " ".join(args)
    try:
        resp = requests.get(f"{API_URL}/api/plaka/{plate}", timeout=10)
        if resp.ok:
            data = resp.json()
            city = data.get("city") or "Bilinmiyor"
            url = data.get("arabam_url", "")
            await update.message.reply_text(
                f"🚗 Plaka: {data['plate']}\n📍 Şehir: {city}\n🔗 {url}"
            )
        else:
            await update.message.reply_text("Plaka sorgulanamadı.")
    except Exception as exc:
        await update.message.reply_text(f"Hata: {exc}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    await update.message.reply_text("⏳ Analiz ediliyor, lütfen bekleyin...")

    if text.startswith("http"):
        try:
            resp = requests.post(f"{API_URL}/api/scrape", json={"url": text}, timeout=30)
            if resp.ok:
                text = resp.json().get("text", text)
            else:
                await update.message.reply_text(
                    f"⚠️ URL okunamadı ({resp.status_code}). Metin olarak işleniyor."
                )
        except Exception:
            pass

    try:
        resp = requests.post(f"{API_URL}/api/analyze", json={"text": text}, timeout=90)
        if not resp.ok:
            detail = resp.json().get("detail", f"HTTP {resp.status_code}")
            await update.message.reply_text(f"❌ Hata: {detail}")
            return

        r = resp.json()
        listing = r.get("listing", {})
        verdict = r.get("verdict", "FAIR")
        emoji = _VERDICT_EMOJI.get(verdict, "🔍")
        verdict_label = _VERDICT_TR.get(verdict, verdict)

        car = " ".join(filter(None, [listing.get("brand"), listing.get("model")])) or "Araç"
        km = listing.get("km")
        km_str = f"{km:,}".replace(",", ".") + " km" if km else "— km"

        msg = (
            f"{emoji} *{verdict_label}* — Skor: {r['opportunity_score']}/100\n\n"
            f"🚗 {car} {listing.get('year') or ''}\n"
            f"📏 {km_str} · {listing.get('fuel_type') or '—'} · {listing.get('transmission') or '—'}\n\n"
            f"💰 İlan fiyatı: {_fmt_price(listing.get('listed_price'))}\n"
            f"📊 Piyasa aralığı: {_fmt_price(r['market_low'])} – {_fmt_price(r['market_high'])}\n"
        )
        if r.get("predicted_price"):
            msg += f"🤖 ML tahmini: {_fmt_price(r['predicted_price'])}\n"

        diff = r.get("price_diff", 0)
        if diff < 0:
            msg += f"📉 Piyasa altı: {_fmt_price(abs(diff))}\n"
        elif diff > 0:
            msg += f"📈 Piyasa üstü: {_fmt_price(diff)}\n"

        msg += f"\n📝 {r.get('expert_comment', '')}"

        pros = r.get("pros", [])
        cons = r.get("cons", [])
        if pros:
            msg += "\n\n✅ Artılar:\n" + "\n".join(f"• {p}" for p in pros[:3])
        if cons:
            msg += "\n\n⚠️ Eksiler:\n" + "\n".join(f"• {c}" for c in cons[:3])

        await update.message.reply_text(msg)

    except Exception as exc:
        await update.message.reply_text(f"❌ Beklenmedik hata: {exc}")


def main() -> None:
    if not TELEGRAM_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN ayarlanmamış. server/.env dosyasına ekleyin."
        )

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("yardim", cmd_yardim))
    app.add_handler(CommandHandler("plaka", cmd_plaka))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print(f"OtoScope Telegram Bot başlatılıyor (API: {API_URL})...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
