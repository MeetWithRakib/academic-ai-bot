# প্রয়োজনীয় লাইব্রেরি ইম্পোর্ট করা
import os
import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
)
import google.generativeai as genai
from flask import Flask
from threading import Thread

# Secrets থেকে টোকেন ও কী লোড করা
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# --- ২৪/৭ বটকে জাগিয়ে রাখার জন্য ওয়েব সার্ভার ---
app = Flask('')

@app.route('/')
def home():
    return "Rakibuzzaman's Academic AI Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
# ----------------------------------------------

# লগিং সেটআপ (সমস্যা নির্ণয়ের জন্য)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Gemini AI কনফিগার করা
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash-latest')

# Conversation states
SELECTING_SUBJECT, ASKING_QUESTION = range(2)

# বই বা বিষয়ের তালিকা
SUBJECTS = {
    "political_theory": "রাজনৈতিক তত্ত্ব: পরিবর্তন ও ধারাবাহিকতা",
    "local_gov": "বাংলাদেশের স্থানীয় সরকার ও পল্লি উন্নয়ন",
    "public_policy": "জননীতি পরিচিতি",
    "east_asia": "পূর্ব এশিয়ার সরকার ও রাজনীতি (চীন, জাপান ও দ. কোরিয়া)",
    "env_dev": "পরিবেশ ও উন্নয়ন",
    "foreign_relations": "বাংলাদেশের বৈদেশিক সম্পর্ক",
    "law_making": "বাংলাদেশের আইন প্রণয়ন প্রক্রিয়া",
    "globalization": "বিশ্বায়ন, আঞ্চলিকতাবাদ ও আন্তর্জাতিক আর্থিক প্রতিষ্ঠান",
    "modern_thought": "আধুনিক রাষ্ট্রচিন্তা"
}

# --- বটের ফাংশনগুলো ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """/start কমান্ড দিলে কথোপকথন শুরু করে এবং বিষয় নির্বাচনের বাটন দেখায়।"""
    logger.info("User %s started the conversation.", update.message.from_user.first_name)
    keyboard = [
        [InlineKeyboardButton(subject, callback_data=key)]
        for key, subject in SUBJECTS.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🎓 স্বাগতম! আমি রাষ্ট্রবিজ্ঞান বিভাগের একজন একাডেমিক অ্যাসিস্ট্যান্ট।\n\n"
        "অনুগ্রহ করে নিচের তালিকা থেকে একটি বিষয় নির্বাচন করুন:",
        reply_markup=reply_markup,
    )
    return SELECTING_SUBJECT

async def subject_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ব্যবহারকারীর নির্বাচিত বিষয় গ্রহণ করে এবং প্রশ্ন করতে বলে।"""
    query = update.callback_query
    await query.answer()

    subject_key = query.data
    logger.info(f"Callback query received with data: {subject_key}")

    subject_name = SUBJECTS.get(subject_key)
    if not subject_name:
        await query.edit_message_text(text="একটি সমস্যা হয়েছে। /start দিয়ে আবার চেষ্টা করুন।")
        return ConversationHandler.END

    context.user_data['selected_subject'] = subject_name

    await query.edit_message_text(
        text=f"আপনি *{subject_name}* বিষয়টি নির্বাচন করেছেন।\n\n"
             f"এখন এই বিষয়ে আপনার প্রশ্নটি লিখুন...",
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ASKING_QUESTION

async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ব্যবহারকারীর প্রশ্ন নিয়ে AI দিয়ে উত্তর তৈরি করে পাঠায়।"""
    user_question = update.message.text
    subject_name = context.user_data.get('selected_subject', 'সাধারণ')

    thinking_message = await update.message.reply_text("আপনার প্রশ্নের উত্তর প্রস্তুত করছি... ✍️")

    # --- সবচেয়ে উন্নত এবং কার্যকর Prompt ---
    prompt = f"""
    You are an expert academic assistant named 'Academic AI Bot', created by Rakibuzzaman for final year Political Science students in Bangladesh.

    **Core Task:**
    Answer the user's question from the subject "{subject_name}". The question is: "{user_question}".
    Your answer must be like a perfect answer from a high-quality academic guide book.

    **Tone and Language Rules (Very Important):**
    1.  **Language Style:** Use simple, clear, and easily understandable formal Bengali (সহজবোধ্য প্রাতিষ্ঠানিক বাংলা). Avoid overly complex, archaic, or difficult words (দুর্বোধ্য শব্দ পরিহার করুন). The goal is for students to read and remember it easily.
    2.  **Tone:** Your tone should be that of a helpful and knowledgeable teacher who makes difficult topics easy.

    **Structure and Formatting Rules (Strictly Follow):**
    1.  **Overall Structure:** The answer must be structured with a 'ভূমিকা' (Introduction), 'মূল আলোচনা' (Main Body), and 'উপসংহার' (Conclusion). Use these exact Bengali words as headings.
    2.  **Headings:** Make the headings (*ভূমিকা*, *মূল আলোচনা*, *উপসংহার*) bold using a single asterisk (*text*).
    3.  **Main Body:**
        - Present information using numbered lists (1., 2., 3.) or bullet points (•).
        - Each point should have a clear, bold subheading (e.g., *১. বিচার বিভাগের স্বাধীনতা*).
        - After the subheading, explain the point in 2-3 simple sentences.
    4.  **Bold Formatting:** Use bold *only* for the main headings (*ভূমিকা*, etc.) and the subheadings within the main body. Do not use bold randomly in the middle of sentences.
    5.  **No Double Asterisks:** Never use `**` for bolding. Only use single asterisks `*`.

    **Example of a good point in the Main Body:**
    *৩. ক্ষমতার ভারসাম্য রক্ষা*
    রাষ্ট্রের তিনটি বিভাগের মধ্যে ক্ষমতার ভারসাম্য রক্ষা করা বিচার বিভাগের অন্যতম প্রধান কাজ। এর মাধ্যমে কোনো একটি বিভাগ যেন অপ্রতিহত ক্ষমতার অধিকারী না হতে পারে, তা নিশ্চিত করা হয়।

    Now, generate the perfect, easy-to-understand, and well-formatted answer.
    """

    try:
        response = await model.generate_content_async(prompt)

        # AI অনেক সময় ডাবল স্টার ব্যবহার করে, তাই এটিকে সিঙ্গেল স্টারে রূপান্তর করা হচ্ছে
        # এটি একটি সেফটি চেক।
        formatted_text = response.text.replace('**', '*')

        await context.bot.edit_message_text(
            text=formatted_text,
            chat_id=update.effective_chat.id,
            message_id=thinking_message.message_id,
            parse_mode=constants.ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.error(f"Error generating or sending content: {e}")
        await context.bot.edit_message_text(
            text="দুঃখিত, একটি প্রযুক্তিগত সমস্যা হয়েছে। অনুগ্রহ করে কিছুক্ষণ পর আবার চেষ্টা করুন।",
            chat_id=update.effective_chat.id,
            message_id=thinking_message.message_id,
        )

    await update.message.reply_text("আপনার আর কোনো প্রশ্ন থাকলে /start কমান্ড দিন।")
    context.user_data.clear()
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "*বট ব্যবহারের নিয়মাবলী:*\n\n"
        "১. `/start` কমান্ড দিন।\n"
        "২. তালিকা থেকে আপনার বিষয়টি বাটনে ক্লিক করে নির্বাচন করুন।\n"
        "৩. এরপর আপনার প্রশ্নটি টাইপ করে পাঠান।\n\n"
        "যেকোনো সময় কার্যক্রম বাতিল করতে /cancel ব্যবহার করুন।"
    )
    await update.message.reply_text(text=help_text, parse_mode=constants.ParseMode.MARKDOWN)

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    about_text = (
        "*Academic AI Bot*\n\n"
        "এই বটটি রাষ্ট্রবিজ্ঞান বিভাগের অনার্স চতুর্থ বর্ষের শিক্ষার্থীদের পড়াশোনায় সহায়তা করার জন্য তৈরি করা হয়েছে।\n\n"
        "*নির্মাতা:*\n"
        "মোঃ রাকিবুজ্জামান\n"
-        "যোগাযোগ: @meetwithrakib"
+       "যোগাযোগ: @meetwithrakib"
    )
    await update.message.reply_text(text=about_text, parse_mode=constants.ParseMode.MARKDOWN)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """কথোপকথন বাতিল করে।"""
    logger.info("User %s canceled the conversation.", update.message.from_user.first_name)
    await update.message.reply_text("কার্যক্রম বাতিল করা হয়েছে। আবার শুরু করতে /start কমান্ড দিন।")
    context.user_data.clear()
    return ConversationHandler.END


def main() -> None:
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # --- Conversation Handler এর সবচেয়ে নির্ভরযোগ্য এবং সরল গঠন ---
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECTING_SUBJECT: [
                CallbackQueryHandler(subject_selected) # কোনো pattern ছাড়াই, সব বাটন ক্লিক গ্রহণ করবে
            ],
            ASKING_QUESTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False # এটি state management কে আরও স্থিতিশীল করে
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about_command))

    keep_alive()
    application.run_polling()

if __name__ == "__main__":
    main()