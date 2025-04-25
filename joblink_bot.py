import os
import asyncio
import json
import requests
from aiogram import Bot, Dispatcher, types
import functools
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor

# Fetch bot token and OpenRouter API key/model from environment or use placeholder defaults
BOT_TOKEN = "8039455940:AAFMHRLkIHM5Ez9Jy5YnAW6WaMmaOSFedlY"
OPENROUTER_API_KEY = "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"
OPENROUTER_MODEL = "openai/gpt-3.5-turbo"

if not BOT_TOKEN or BOT_TOKEN.startswith("<"):
    raise Exception("Missing BOT_TOKEN environment variable.")
if not OPENROUTER_API_KEY or OPENROUTER_API_KEY.startswith("<"):
    raise Exception("Missing OPENROUTER_API_KEY environment variable.")
if not OPENROUTER_MODEL:
    raise Exception("Missing OPENROUTER_MODEL environment variable.")

# Initialize bot and dispatcher with in-memory storage for FSM
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Define supported languages and their native names
LANGUAGES = {
    'en': 'English',
    'ru': 'Русский',
    'kk': 'Қазақша',
    'es': 'Español',
    'fr': 'Français'
}

# Define translations for menu options and static prompts in each language
MENU_TEXT = {
    'job_search': {
        'en': '🌐 Job Search',
        'ru': '🌐 Поиск работы',
        'kk': '🌐 Жұмыс іздеу',
        'es': '🌐 Búsqueda de empleo',
        'fr': '🌐 Recherche d\'emploi'
    },
    'career_test': {
        'en': '📝 Career Test',
        'ru': '📝 Карьерный тест',
        'kk': '📝 Мансаптық тест',
        'es': '📝 Test de carrera',
        'fr': '📝 Test de carrière'
    },
    'interview_prep': {
        'en': '💼 Interview Prep',
        'ru': '💼 Подготовка к интервью',
        'kk': '💼 Сұхбатқа дайындық',
        'es': '💼 Preparación para entrevista',
        'fr': '💼 Préparation à l\'entretien'
    },
    'back': {
        'en': '↩️ Back',
        'ru': '↩️ Назад',
        'kk': '↩️ Артқа',
        'es': '↩️ Atrás',
        'fr': '↩️ Retour'
    },
    'clear': {
        'en': '❌ Clear',
        'ru': '❌ Сброс',
        'kk': '❌ Тазалау',
        'es': '❌ Reiniciar',
        'fr': '❌ Réinitialiser'
    }
}

PROMPTS = {
    'choose_language': """Please select a language / Выберите язык / Тілді таңдаңыз / Seleccione el idioma / Choisissez la langue:
🇬🇧 English
🇷🇺 Русский
🇰🇿 Қазақша
🇪🇸 Español
🇫🇷 Français""",
    'choose_option': {
        'en': 'Please choose an option below:',
        'ru': 'Пожалуйста, выберите один из вариантов:',
        'kk': 'Нұсқалардың бірін таңдаңыз:',
        'es': 'Por favor, elija una opción:',
        'fr': 'Veuillez choisir une option:'
    },
    'enter_position': {
        'en': 'Please enter the job position/title for the interview simulation:',
        'ru': 'Пожалуйста, введите должность для симуляции интервью:',
        'kk': 'Сұхбат симуляциясы үшін қызмет атауын енгізіңіз:',
        'es': 'Por favor, introduzca el puesto para la simulación de entrevista:',
        'fr': 'Veuillez saisir le poste pour la simulation d\'entretien:'
    },
    'analyzing': {
        'en': '🔍 Analyzing answers...',
        'ru': '🔍 Анализируем ответы...',
        'kk': '🔍 Жауаптар талдануда...',
        'es': '🔍 Analizando respuestas...',
        'fr': '🔍 Analyse des réponses...'
    },
    'generating': {
        'en': '📝 Generating text...',
        'ru': '📝 Генерируем текст...',
        'kk': '📝 Мәтін жасалуда...',
        'es': '📝 Generando texto...',
        'fr': '📝 Génération du texte...'
    },
    'return_main': {
        'en': 'You can now choose another option from the main menu.',
        'ru': 'Теперь вы можете выбрать другую опцию из главного меню.',
        'kk': 'Енді басты мәзірден басқа опцияны таңдай аласыз.',
        'es': 'Ahora puede elegir otra opción del menú principal.',
        'fr': 'Vous pouvez maintenant choisir une autre option du menu principal.'
    }
}

# FSM state definitions for different conversation flows
class JobSearchState(StatesGroup):
    asking = State()  # in job search Q&A

class CareerTestState(StatesGroup):
    asking = State()  # in career test Q&A

class InterviewState(StatesGroup):
    position = State()  # waiting for position input
    asking = State()    # in interview Q&A

# Helper function to call OpenRouter API for a given conversation (list of messages)
async def call_openrouter_api(messages):
    headers = {
        'Authorization': f'Bearer {OPENROUTER_API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': OPENROUTER_MODEL,
        'messages': messages
    }
    # Use run_in_executor to avoid blocking on the requests call
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        functools.partial(requests.post, 'https://openrouter.ai/api/v1/chat/completions', headers=headers, json=payload)
    )
    if response.status_code == 200:
        data = response.json()
        try:
            content = data['choices'][0]['message']['content']
        except (KeyError, IndexError):
            content = ''
        return content.strip()
    else:
        # On error, return an error message or raise exception as needed
        return "(Error: AI response failed)"

# Handler for /start and /clear commands (and "Clear" button) to reset and choose language
@dp.message_handler(commands=['start', 'clear'], state='*')
@dp.message_handler(lambda message: message.text and message.text.strip() in [MENU_TEXT['clear'][lang] for lang in MENU_TEXT['clear']], state='*')
async def cmd_start_clear(message: types.Message, state: FSMContext):
    # End any ongoing conversation state
    await state.finish()
    # Create keyboard for language options
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for code, lang_name in LANGUAGES.items():
        keyboard.add(types.KeyboardButton(lang_name))
    # Send language selection prompt
    await message.reply(PROMPTS['choose_language'], reply_markup=keyboard)

# Handler for language selection
@dp.message_handler(lambda message: message.text in LANGUAGES.values(), state='*')
async def language_chosen(message: types.Message, state: FSMContext):
    # Identify chosen language code
    lang_code = None
    for code, name in LANGUAGES.items():
        if message.text == name:
            lang_code = code
            break
    if not lang_code:
        return  # Unrecognized language (should not happen)
    # Store chosen language
    await state.update_data(lang=lang_code)
    # Build main menu keyboard in the selected language
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton(MENU_TEXT['job_search'][lang_code]))
    kb.add(types.KeyboardButton(MENU_TEXT['career_test'][lang_code]))
    kb.add(types.KeyboardButton(MENU_TEXT['interview_prep'][lang_code]))
    kb.add(types.KeyboardButton(MENU_TEXT['clear'][lang_code]))
    # Prompt user to choose a mode
    await message.reply(PROMPTS['choose_option'][lang_code], reply_markup=kb)

# Handler for selecting Job Search mode
@dp.message_handler(lambda message: message.text and any(message.text == MENU_TEXT['job_search'][lang] for lang in LANGUAGES.keys()), state='*')
async def start_job_search(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'en')
    # Prepare system prompt for job search mode
    system_prompt = (
        f"You are a helpful career assistant helping a user search for a job. "
        f"Ask the user a series of adaptive questions (for example, about desired position, experience, skills, expectations, etc.) based on their previous answers. "
        f"Ask one question at a time. Stop asking questions when you have gathered enough information to make job suggestions. "
        f"Then, instead of a question, provide the user with a list of job suggestions (3-5 positions) and a brief summary of their information. "
        f"The conversation should be in {LANGUAGES[lang]}. Do not switch languages. "
        f"Do not mention that you are an AI. Do not ask additional questions after providing the suggestions."
    )
    # Initialize conversation history for this mode
    conversation = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': 'Begin job search dialog'}
    ]
    await state.update_data(conv=conversation, lang=lang)
    # Query AI for the first question
    reply = await call_openrouter_api(conversation)
    if not reply:
        reply = "(AI did not provide a response)"
    # Append the assistant's question to the conversation history
    conversation.append({'role': 'assistant', 'content': reply})
    await state.update_data(conv=conversation)
    # Send first question with Back/Clear options
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton(MENU_TEXT['back'][lang])).add(types.KeyboardButton(MENU_TEXT['clear'][lang]))
    await JobSearchState.asking.set()
    await message.reply(reply, reply_markup=kb)

# Handler for user answers in Job Search mode
@dp.message_handler(state=JobSearchState.asking)
async def job_search_answer(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'en')
    user_text = message.text.strip() if message.text else ''
    # Check for Back or Clear commands
    if user_text == MENU_TEXT['back'][lang]:
        # Go back to main menu
        await state.finish()
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(types.KeyboardButton(MENU_TEXT['job_search'][lang]))
        kb.add(types.KeyboardButton(MENU_TEXT['career_test'][lang]))
        kb.add(types.KeyboardButton(MENU_TEXT['interview_prep'][lang]))
        kb.add(types.KeyboardButton(MENU_TEXT['clear'][lang]))
        await message.reply(PROMPTS['return_main'][lang], reply_markup=kb)
        return
    if user_text == MENU_TEXT['clear'][lang]:
        # Reset session to language selection
        await state.finish()
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for code, lang_name in LANGUAGES.items():
            keyboard.add(types.KeyboardButton(lang_name))
        await message.reply(PROMPTS['choose_language'], reply_markup=keyboard)
        return
    # Otherwise, treat the message as an answer to the last question
    conv = data.get('conv', [])
    if not conv:
        # If conversation history is missing, reset to main menu
        await state.finish()
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(types.KeyboardButton(MENU_TEXT['job_search'][lang]))
        kb.add(types.KeyboardButton(MENU_TEXT['career_test'][lang]))
        kb.add(types.KeyboardButton(MENU_TEXT['interview_prep'][lang]))
        kb.add(types.KeyboardButton(MENU_TEXT['clear'][lang]))
        await message.reply(PROMPTS['return_main'][lang], reply_markup=kb)
        return
    # Append user's answer to conversation
    conv.append({'role': 'user', 'content': message.text})
    # Get AI response (next question or final suggestions)
    reply = await call_openrouter_api(conv)
    if not reply:
        reply = "(AI did not provide a response)"
    # If the AI's reply ends with a question mark, it's another question
    if reply.rstrip().endswith('?'):
        conv.append({'role': 'assistant', 'content': reply})
        await state.update_data(conv=conv)
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(types.KeyboardButton(MENU_TEXT['back'][lang])).add(types.KeyboardButton(MENU_TEXT['clear'][lang]))
        await message.reply(reply, reply_markup=kb)
    else:
        # Final output (suggestions and summary) detected
        await message.reply(PROMPTS['analyzing'][lang])
        await asyncio.sleep(1)
        await message.reply(PROMPTS['generating'][lang])
        await asyncio.sleep(1)
        await message.reply(reply)
        # End job search mode and return to main menu
        await state.finish()
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(types.KeyboardButton(MENU_TEXT['job_search'][lang]))
        kb.add(types.KeyboardButton(MENU_TEXT['career_test'][lang]))
        kb.add(types.KeyboardButton(MENU_TEXT['interview_prep'][lang]))
        kb.add(types.KeyboardButton(MENU_TEXT['clear'][lang]))
        await message.reply(PROMPTS['return_main'][lang], reply_markup=kb)

# Handler for selecting Career Test mode
@dp.message_handler(lambda message: message.text and any(message.text == MENU_TEXT['career_test'][lang] for lang in LANGUAGES.keys()), state='*')
async def start_career_test(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'en')
    # Prepare system prompt for career test mode (15 questions)
    system_prompt = (
        f"You are a career guidance counselor administering a career aptitude test with 15 questions. "
        f"Ask the user 15 questions one by one about their preferences, personal qualities, logic and thinking. "
        f"Make sure the questions are diverse and not formulaic. "
        f"Do not provide any results or analysis until all 15 questions have been answered. "
        f"The conversation should be in {LANGUAGES[lang]}."
    )
    conversation = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': 'Begin the career test'}
    ]
    await state.update_data(conv=conversation, lang=lang, question_count=1)  # question_count=1 for Q1 about to be asked
    # Get first question from AI
    reply = await call_openrouter_api(conversation)
    if not reply:
        reply = "(AI did not provide a response)"
    # Append first question
    conversation.append({'role': 'assistant', 'content': reply})
    await state.update_data(conv=conversation, question_count=1)  # Q1 asked
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton(MENU_TEXT['back'][lang])).add(types.KeyboardButton(MENU_TEXT['clear'][lang]))
    await CareerTestState.asking.set()
    await message.reply(reply, reply_markup=kb)

# Handler for user answers in Career Test mode
@dp.message_handler(state=CareerTestState.asking)
async def career_test_answer(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'en')
    user_text = message.text.strip() if message.text else ''
    # Handle Back or Clear during test
    if user_text == MENU_TEXT['back'][lang]:
        await state.finish()
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(types.KeyboardButton(MENU_TEXT['job_search'][lang]))
        kb.add(types.KeyboardButton(MENU_TEXT['career_test'][lang]))
        kb.add(types.KeyboardButton(MENU_TEXT['interview_prep'][lang]))
        kb.add(types.KeyboardButton(MENU_TEXT['clear'][lang]))
        await message.reply(PROMPTS['return_main'][lang], reply_markup=kb)
        return
    if user_text == MENU_TEXT['clear'][lang]:
        await state.finish()
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for code, lang_name in LANGUAGES.items():
            keyboard.add(types.KeyboardButton(lang_name))
        await message.reply(PROMPTS['choose_language'], reply_markup=keyboard)
        return
    # Otherwise, treat as answer to a test question
    conv = data.get('conv', [])
    q_count = data.get('question_count', 0)
    if not conv or q_count is None:
        # If lost context, reset to main menu
        await state.finish()
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(types.KeyboardButton(MENU_TEXT['job_search'][lang]))
        kb.add(types.KeyboardButton(MENU_TEXT['career_test'][lang]))
        kb.add(types.KeyboardButton(MENU_TEXT['interview_prep'][lang]))
        kb.add(types.KeyboardButton(MENU_TEXT['clear'][lang]))
        await message.reply(PROMPTS['return_main'][lang], reply_markup=kb)
        return
    # Append the user's answer
    conv.append({'role': 'user', 'content': message.text})
    # Determine how many questions have been asked so far (q_count represents the last question number asked)
    if q_count < 15:
        # Ask next question
        reply = await call_openrouter_api(conv)
        if not reply:
            reply = "(AI did not provide a response)"
        conv.append({'role': 'assistant', 'content': reply})
        q_count += 1
        await state.update_data(conv=conv, question_count=q_count)
        # If not yet the last question, send it and continue
        if q_count < 15:
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            kb.add(types.KeyboardButton(MENU_TEXT['back'][lang])).add(types.KeyboardButton(MENU_TEXT['clear'][lang]))
            await message.reply(reply, reply_markup=kb)
            return
        else:
            # If this was the 15th question, send it and wait for the final answer
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            kb.add(types.KeyboardButton(MENU_TEXT['back'][lang])).add(types.KeyboardButton(MENU_TEXT['clear'][lang]))
            await message.reply(reply, reply_markup=kb)
            return
    # If q_count >= 15, it means the user has just answered the 15th question
    # Prepare the analysis prompt with all Q&A
    qa_text = ""
    qnum = 0
    for msg in conv:
        if msg['role'] == 'assistant':
            qnum += 1
            qa_text += f"{qnum}. {msg['content']}\n"
        elif msg['role'] == 'user' and qnum > 0:
            qa_text += f"Answer: {msg['content']}\n\n"
    analysis_prompt = (
        f"The user has completed a career test with 15 questions. Here are the questions and the user's answers:\n"
        f"{qa_text}"
        f"Based on the user's answers, suggest a few suitable professions/career paths for the user and explain why those would be a good fit."
    )
    analysis_conv = [
        {'role': 'system', 'content': f"You are a career counselor providing guidance in {LANGUAGES[lang]}."},
        {'role': 'user', 'content': analysis_prompt}
    ]
    # Show typing feedback
    await message.reply(PROMPTS['analyzing'][lang])
    await asyncio.sleep(1)
    await message.reply(PROMPTS['generating'][lang])
    # Call AI for analysis
    result = await call_openrouter_api(analysis_conv)
    if not result:
        result = "(AI did not provide a response)"
    # Send the analysis result
    await message.reply(result)
    # End test mode and return to main menu
    await state.finish()
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton(MENU_TEXT['job_search'][lang]))
    kb.add(types.KeyboardButton(MENU_TEXT['career_test'][lang]))
    kb.add(types.KeyboardButton(MENU_TEXT['interview_prep'][lang]))
    kb.add(types.KeyboardButton(MENU_TEXT['clear'][lang]))
    await message.reply(PROMPTS['return_main'][lang], reply_markup=kb)

# Handler for selecting Interview Prep mode
@dp.message_handler(lambda message: message.text and any(message.text == MENU_TEXT['interview_prep'][lang] for lang in LANGUAGES.keys()), state='*')
async def start_interview_prep(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'en')
    # Ask the user for the position they want to practice
    await InterviewState.position.set()
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton(MENU_TEXT['back'][lang])).add(types.KeyboardButton(MENU_TEXT['clear'][lang]))
    await message.reply(PROMPTS['enter_position'][lang], reply_markup=kb)

# Handler for receiving the desired position
@dp.message_handler(state=InterviewState.position)
async def interview_position_received(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'en')
    user_text = message.text.strip() if message.text else ''
    if user_text == MENU_TEXT['back'][lang]:
        # Cancel and return to menu
        await state.finish()
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(types.KeyboardButton(MENU_TEXT['job_search'][lang]))
        kb.add(types.KeyboardButton(MENU_TEXT['career_test'][lang]))
        kb.add(types.KeyboardButton(MENU_TEXT['interview_prep'][lang]))
        kb.add(types.KeyboardButton(MENU_TEXT['clear'][lang]))
        await message.reply(PROMPTS['return_main'][lang], reply_markup=kb)
        return
    if user_text == MENU_TEXT['clear'][lang]:
        await state.finish()
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for code, lang_name in LANGUAGES.items():
            keyboard.add(types.KeyboardButton(lang_name))
        await message.reply(PROMPTS['choose_language'], reply_markup=keyboard)
        return
    # We have the position input
    position = message.text
    # Prepare system prompt for interview mode
    system_prompt = (
        f"You are a job interviewer conducting a practice interview for a {position} position. "
        f"Ask the candidate 10 interview questions one by one, relevant to the {position} role (including both technical and behavioral questions if applicable). "
        f"Do not provide any evaluation or feedback until the interview is complete. "
        f"The conversation should be in {LANGUAGES[lang]}."
    )
    conversation = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': f"Begin the interview for the {position} position."}
    ]
    await state.update_data(conv=conversation, lang=lang, position=position, question_count=1)
    # Get first interview question from AI
    reply = await call_openrouter_api(conversation)
    if not reply:
        reply = "(AI did not provide a response)"
    conversation.append({'role': 'assistant', 'content': reply})
    await state.update_data(conv=conversation, question_count=1)
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton(MENU_TEXT['back'][lang])).add(types.KeyboardButton(MENU_TEXT['clear'][lang]))
    await InterviewState.asking.set()
    await message.reply(reply, reply_markup=kb)

# Handler for user answers in Interview Prep mode
@dp.message_handler(state=InterviewState.asking)
async def interview_answer(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'en')
    position = data.get('position', '')
    user_text = message.text.strip() if message.text else ''
    # Handle Back or Clear during interview
    if user_text == MENU_TEXT['back'][lang]:
        await state.finish()
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(types.KeyboardButton(MENU_TEXT['job_search'][lang]))
        kb.add(types.KeyboardButton(MENU_TEXT['career_test'][lang]))
        kb.add(types.KeyboardButton(MENU_TEXT['interview_prep'][lang]))
        kb.add(types.KeyboardButton(MENU_TEXT['clear'][lang]))
        await message.reply(PROMPTS['return_main'][lang], reply_markup=kb)
        return
    if user_text == MENU_TEXT['clear'][lang]:
        await state.finish()
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for code, lang_name in LANGUAGES.items():
            keyboard.add(types.KeyboardButton(lang_name))
        await message.reply(PROMPTS['choose_language'], reply_markup=keyboard)
        return
    # Otherwise, treat as answer to interview question
    conv = data.get('conv', [])
    q_count = data.get('question_count', 0)
    if not conv or q_count is None or not position:
        # Lost context, go back to menu
        await state.finish()
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(types.KeyboardButton(MENU_TEXT['job_search'][lang]))
        kb.add(types.KeyboardButton(MENU_TEXT['career_test'][lang]))
        kb.add(types.KeyboardButton(MENU_TEXT['interview_prep'][lang]))
        kb.add(types.KeyboardButton(MENU_TEXT['clear'][lang]))
        await message.reply(PROMPTS['return_main'][lang], reply_markup=kb)
        return
    # Append user's answer
    conv.append({'role': 'user', 'content': message.text})
    # Continue asking questions if not yet 10
    if q_count < 10:
        reply = await call_openrouter_api(conv)
        if not reply:
            reply = "(AI did not provide a response)"
        conv.append({'role': 'assistant', 'content': reply})
        q_count += 1
        await state.update_data(conv=conv, question_count=q_count)
        if q_count < 10:
            # Send next question
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            kb.add(types.KeyboardButton(MENU_TEXT['back'][lang])).add(types.KeyboardButton(MENU_TEXT['clear'][lang]))
            await message.reply(reply, reply_markup=kb)
            return
        else:
            # If this was the 10th question, send it and wait for the final answer
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            kb.add(types.KeyboardButton(MENU_TEXT['back'][lang])).add(types.KeyboardButton(MENU_TEXT['clear'][lang]))
            await message.reply(reply, reply_markup=kb)
            return
    # If q_count >= 10, the user has answered the 10th question
    # Compile the Q&A for analysis
    qa_text = ""
    qnum = 0
    for msg in conv:
        if msg['role'] == 'assistant':
            qnum += 1
            qa_text += f"Q{qnum}: {msg['content']}\n"
        elif msg['role'] == 'user' and qnum > 0:
            qa_text += f"A{qnum}: {msg['content']}\n\n"
    analysis_prompt = (
        f"Position: {position}\n"
        f"Interview questions and candidate's answers:\n{qa_text}"
        f"Now evaluate the candidate's performance for the {position} interview. Decide if they passed the interview or not, and provide an explanation with recommendations for improvement."
    )
    analysis_conv = [
        {'role': 'system', 'content': f"You are an HR expert providing interview feedback in {LANGUAGES[lang]}."},
        {'role': 'user', 'content': analysis_prompt}
    ]
    # Show typing indicators
    await message.reply(PROMPTS['analyzing'][lang])
    await asyncio.sleep(1)
    await message.reply(PROMPTS['generating'][lang])
    # Get interview feedback from AI
    result = await call_openrouter_api(analysis_conv)
    if not result:
        result = "(AI did not provide a response)"
    await message.reply(result)
    # End interview mode and return to main menu
    await state.finish()
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton(MENU_TEXT['job_search'][lang]))
    kb.add(types.KeyboardButton(MENU_TEXT['career_test'][lang]))
    kb.add(types.KeyboardButton(MENU_TEXT['interview_prep'][lang]))
    kb.add(types.KeyboardButton(MENU_TEXT['clear'][lang]))
    await message.reply(PROMPTS['return_main'][lang], reply_markup=kb)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
