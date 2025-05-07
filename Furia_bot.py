import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from datetime import datetime
from bs4 import BeautifulSoup
from config import TOKEN, RAPIDAPI_KEY, INSTAGRAM_USERNAME, RESPOSTA_CORRETA, HLTV_API_URL
import requests

# Configuração inicial
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Variável global para pontuação do quiz
user_quizzes = {}

# Função para o comando /start com menu interativo
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📰 Notícias", callback_data='noticias')],
        [InlineKeyboardButton("🎮 Próximos Jogos", callback_data='proximos_jogos')],
        [InlineKeyboardButton("📖 História", callback_data='historia')],
        [InlineKeyboardButton("❓ Quiz", callback_data='quiz')],
        [InlineKeyboardButton("📸 Stories", callback_data='stories')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        '🐍 Bem-vindo ao Bot da FURIA! Escolha uma opção:',
        reply_markup=reply_markup
    )

# Handler para botões inline
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'noticias':
        await noticias(update, context)
    elif query.data == 'proximos_jogos':
        await proximos_jogos(update, context)
    elif query.data == 'historia':
        await historia(update, context)
    elif query.data == 'quiz':
        await quiz(update, context)
    elif query.data == 'stories':
        await stories(update, context)

async def stories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Buscando os últimos stories da FURIA...")

        url = "https://instagram-scraper-stable-api.p.rapidapi.com/get_ig_user_stories.php"
        payload = {'username_or_url': INSTAGRAM_USERNAME}
        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": "instagram-scraper-stable-api.p.rapidapi.com"
        }

        response = requests.post(url, data=payload, headers=headers, timeout=10)

        if response.status_code == 200:
            stories_data = response.json()
            enviados = 0
            
            if not isinstance(stories_data, list):
                await context.bot.send_message(chat_id=update.effective_chat.id, text="Formato de stories inválido.")
                return

            for story in stories_data:
                try:
                    if 'video_versions' in story and story['video_versions']:
                        video_url = story['video_versions'][0]['url']
                        await context.bot.send_video(
                            chat_id=update.effective_chat.id,
                            video=video_url,
                            supports_streaming=True
                        )
                        enviados += 1
                    elif 'image_versions2' in story and story['image_versions2']['candidates']:
                        img_url = story['image_versions2']['candidates'][0]['url']
                        await context.bot.send_photo(
                            chat_id=update.effective_chat.id,
                            photo=img_url
                        )
                        enviados += 1
                    if enviados >= 3:
                        break
                        
                except Exception as e:
                    logger.error(f"Erro ao enviar story: {e}")
                    continue
            
            if enviados == 0:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="Nenhum story disponível no momento.")
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Erro ao acessar os stories. Tente novamente mais tarde.")
            logger.error(f"Erro na API de stories: {response.status_code} - {response.text}")

    except Exception as e:
        logger.error(f"Erro geral em stories: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Ocorreu um erro inesperado. Tente novamente mais tarde.")

# API para posts do instagram
def obter_ultimos_posts():
    try:
        url = "https://instagram-scraper-stable-api.p.rapidapi.com/get_ig_user_posts.php"
        
        payload = {
            "username_or_url": "furiagg",
            "amount": "3"
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": "instagram-scraper-stable-api.p.rapidapi.com"
        }

        response = requests.post(url, headers=headers, data=payload, timeout=10)
        
        if response is None:
            logger.error("Nenhuma resposta recebida da API")
            return None
            
        if response.status_code != 200:
            logger.error(f"Erro na API: {response.status_code} - {response.text}")
            return None

        try:
            data = response.json()
        except ValueError:
            logger.error("Resposta da API não é um JSON válido")
            return None

        if not data or not isinstance(data, dict):
            logger.error("Resposta da API em formato inválido")
            return None

        if 'posts' not in data:
            logger.error("Campo 'posts' não encontrado na resposta")
            return None

        posts = []
        for post in data['posts']:
            try:
                node = post.get('node', {})
                if not node:
                    continue

                caption = node.get('caption', {})
                media_url = ''
                is_video = False

                # Verifica se é vídeo
                if 'video_versions' in node and node['video_versions']:
                    is_video = True
                    media_url = node['video_versions'][0].get('url', '')
                elif 'image_versions2' in node:
                    candidates = node['image_versions2'].get('candidates', [])
                    if candidates:
                        media_url = candidates[0].get('url', '')

                posts.append({
                    'caption': caption.get('text', 'Sem descrição'),
                    'media_url': media_url,
                    'is_video': is_video,
                    'timestamp': node.get('taken_at'),
                    'post_id': node.get('id')
                })
            except Exception as post_error:
                logger.error(f"Erro ao processar post: {post_error}")
                continue

        return posts if posts else None

    except requests.exceptions.RequestException as e:
        logger.error(f"Erro de conexão: {e}")
        return None
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        return None
            
# Comando /noticias
async def noticias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        posts = obter_ultimos_posts()
        
        if not posts:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Não foi possível obter os posts no momento.")
            return

        for post in posts:
            try:
                caption = post['caption'][:1000] if post['caption'] else "Novo post da FURIA!"
                
                if post['is_video']:
                    await context.bot.send_video(
                        chat_id=update.effective_chat.id,
                        video=post['media_url'],
                        caption=caption
                    )
                else:
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=post['media_url'],
                        caption=caption
                    )
            except Exception as e:
                logger.error(f"Erro ao enviar post: {e}")
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"{caption}\n\n(Conteúdo não disponível)"
                )

    except Exception as e:
        logger.error(f"Erro geral em notícias: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Ocorreu um erro ao buscar as notícias.")

# API para comando /proximosjogos
async def get_furia_matches():
    try:
        url = "https://hltv-api.vercel.app/api/matches"  # API community alternativa
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        matches = response.json()
        
        furia_matches = [
            match for match in matches 
            if match.get('team1', {}).get('name') == 'FURIA' or 
               match.get('team2', {}).get('name') == 'FURIA'
        ]
        
        if furia_matches:
            formatted_matches = []
            for match in furia_matches[:3]:  # Limita a 3 jogos
                formatted_matches.append({
                    'time': datetime.fromtimestamp(match['date']/1000).strftime('%d/%m %H:%M'),
                    'teams': [match['team1']['name'], match['team2']['name']],
                    'event': match['event']['name']
                })
            return formatted_matches

    except Exception as api_error:
        logger.warning(f"API falhou: {api_error}")


    try:
        url = "https://www.hltv.org/team/8297/furia"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        matches = []
        for match in soup.select('.upcomingMatch'):
            team1 = match.select_one('.matchTeam1 .team').text.strip()
            team2 = match.select_one('.matchTeam2 .team').text.strip()
            
            if 'FURIA' in (team1.upper(), team2.upper()):
                matches.append({
                    'time': match.select_one('.matchTime').get('data-unix'),  # Timestamp em ms
                    'teams': [team1, team2],
                    'event': match.select_one('.matchEvent .event').text.strip()
                })
        
        if matches:
            formatted_matches = []
            for match in matches[:3]:
                formatted_matches.append({
                    'time': datetime.fromtimestamp(int(match['time'])/1000).strftime('%d/%m %H:%M'),
                    'teams': match['teams'],
                    'event': match['event']
                })
            return formatted_matches

    except Exception as scrape_error:
        logger.error(f"Scraping falhou: {scrape_error}")

    return [{
        'time': datetime.now().strftime('%d/%m %H:%M'),
        'teams': ["FURIA", "Time Desconhecido"],
        'event': "Próxima Partida"
    }]
    

# Comando /proximosjogos
async def proximos_jogos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        matches = await get_furia_matches()  # Sua função de obtenção de jogos
        
        if not matches or len(matches) == 0:
            # Mensagem especial quando não há jogos
            await context.bot.send_message(
                chat_id=chat_id,
                text="📭 A FURIA não tem jogos agendados no momento.\n\n"
                     "🔔 Volte mais tarde ou confira o calendário completo:\n"
                     "👉 https://www.hltv.org/team/8297/furia#tab-matches",
                disable_web_page_preview=True
            )
            return

        # Restante do código para mostrar os jogos...
        mensagem = "🐍 **Próximos Jogos da FURIA**\n\n"
        for match in matches:
            adversario = match['teams'][1] if match['teams'][0] == 'FURIA' else match['teams'][0]
            mensagem += (
                f"⏰ {match['time']}\n"
                f"⚔️ FURIA vs {adversario}\n"
                f"🏆 {match['event']}\n\n"
            )

        await context.bot.send_message(
            chat_id=chat_id,
            text=mensagem,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📅 Ver Calendário Completo", url="https://www.hltv.org/team/8297/furia#tab-matches")
            ]])
        )

    except Exception as e:
        logger.error(f"Erro: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ Estamos com dificuldades para acessar os dados. Você pode verificar diretamente no site:\n"
                 "🔗 https://www.hltv.org/team/8297/furia",
            disable_web_page_preview=True
        )

# Comando /historia          
async def historia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensagem = (
        "📜 História da FURIA:\n\n"
        "A FURIA Esports foi fundada em 2017 e se tornou um dos times de CS:GO mais respeitados "
        "da América Latina! Conhecida por seu estilo agressivo e pela paixão de seus jogadores, "
        "a FURIA já conquistou diversos títulos internacionais. 🐍🔥"
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=mensagem)
    
# Comando
async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Quiz: Em que ano a FURIA foi fundada?\n1) 2015\n2) 2017\n3) 2019')


async def processar_resposta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    resposta = update.message.text.strip()
    
    if resposta == resposta_correta:
        await update.message.reply_text('Resposta correta! 🎉 A FURIA foi fundada em 2017.')
    else:
        await update.message.reply_text(f'Ops, resposta errada! Tente novamente. A resposta correta é: {resposta_correta}.')

# Configuração do bot
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("noticias", noticias))
    app.add_handler(CommandHandler("proximosjogos", proximos_jogos))
    app.add_handler(CommandHandler("historia", historia))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(CommandHandler("stories", stories))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, processar_resposta))
    
    # Inicia o bot
    app.run_polling()

if __name__ == "__main__":
    main()