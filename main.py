import os
from dotenv import load_dotenv
from dataclasses import dataclass, asdict
import os
import openai
from metaphor_python import Metaphor
import html2text
from gtts import gTTS, lang

# set up environment
load_dotenv()

# Class represents information about the articles collected (title, author, published date, content, url)
@dataclass
class Article:
    title: str
    author: str
    published_date: str
    content: str
    summary : str
    url: str

    # Represents instance as dictionary
    def dict(self) -> dict:
        return asdict(self)

# Class represents the text to speech service (find articles, translation, SSML conversion, audio generation)
class Audicle:
    
    # Message codes used
    generate_query_message = "You are a helpful assistant that generates search queries based on user questions. Only generate one search query. The query should help find articles related to the users query. If the user uses abbreviations, expand these to full phrases. If the user inputs something you don’t understand, look for the articles closest to their search."
    summarize_text_message = "You are a helpful assistant that summarizes the content of a webpage. Summarize the user's input. Only output the summary."
    text_to_ssml_message = "You are a helpful assistant that converts extracted HTML text to SSML using Google Cloud's SSML reference. Convert the user's input while retaining the semantic meaning. Only output the SSML text."
    clean_message = "You are a helpful assistant that makes sure that sentences make sense logically and grammatically based on user input. Make sure the sentence flows correctly and is grammatically correct. Wherever it says null, ignore these fields and continue."

    # Supported language conversions
    supported_lang =  {k: v.lower() for k, v in lang.tts_langs().items()}

    def __init__(self):
        
        self.openai_key = os.getenv('OPENAI_API_KEY')
        openai.api_key = self.openai_key
        self.metaphor = Metaphor(os.getenv('METAPHOR_API_KEY'))

    def main(self) -> None:

        # Ask user prelim questions for inputs
        topic = input("Hello! Thanks for using Audicle. What kind of article do you want to read today?\n")

        # Make sure requested language is supported
        listen_lang = input("Great! Is there a specific language you'd like to listen in? Please write out the full name of the language.\n")
        while listen_lang.lower() not in self.supported_lang.values():
            listen_lang = input("Sorry, that language is not supported. Please select a language from this list: https://cloud.google.com/text-to-speech/docs/voices\n")

        # Generate query
        query = self.generate(self.generate_query_message, topic)

        print("Loading your article...")

        # Seach for primary article and extract contents
        article = self.metaphor.search(query, num_results = 1, use_autoprompt=True)
        article_list = []
        contents = article.get_contents().contents
        result = article.results
        for i in range(len(contents)):
            article_list.append(self.scrape(result[i].title, result[i].author, result[i].published_date, contents[i].extract, contents[i].url, contents[i].id))

        # Find similar articles and extract contents
        similar_articles = self.metaphor.find_similar(url = article_list[0].url, num_results = 3)
        contents = similar_articles.get_contents().contents
        result = similar_articles.results
        for i in range(len(contents)):
            article_list.append(self.scrape(result[i].title, result[i].author, result[i].published_date, contents[i].extract, contents[i].url, contents[i].id))

        # Assign name to each article
        main, similar1, similar2, similar3 = [i for i in article_list]

        # Give audio file + thanks for listening message
        self.audio_file(main, similar1, similar2, similar3, listen_lang)
        print(self.thanks_for_listening(main, similar1, similar2, similar3))

    # Generate appropriate text output based on user input
    def generate(self, message: str, query: str) -> str:
        completion = openai.ChatCompletion.create(
            model = "gpt-3.5-turbo",
            messages = [
                {"role": "system", "content": message},
                {"role": "user", "content": query},
            ]
        )
        return completion.choices[0].message.content

    # Extract content from query output to create list of Articles
    def scrape(self, title: str, author: str, date: str, content: str, url: str, id_num: str) -> Article:
        article_temp = Article(title = title, author = author, published_date = date, content = content, summary = content, url = url)
        self.get_contents(article_temp, id_num)
        self.html_to_plain(article_temp)
        self.summarize(article_temp)
        return article_temp

    # Retrieve contents
    def get_contents(self, article: Article, id_num = str) -> None:
        content = self.metaphor.get_contents(id_num)
        for content in content.contents:
            article.content = content.extract

    # Convert extracted HTML text to plain text
    def html_to_plain(self, article: Article) -> None:
        convert = html2text.html2text(article.content)
        article.content = convert

    # Update content summary
    def summarize(self, article: Article) -> None:
        summary = self.generate(self.summarize_text_message, article.content)
        article.summary = summary

    # Generate standard reading format ("script") for audio generation
    def text_to_script(self, main: Article, first: Article, second: Article, third: Article) -> str:
        script = f"Here is {main.title} written by {main.author} on {main.published_date}. {main.content}. For further reading, check out {first.title} by {first.author} which discusses {first.summary}. Additionally, you can check out {second.title} by {second.author} or {third.title} by {third.author}."
        script = self.generate(self.clean_message, script)
        return script
        #return self.generate(self.text_to_ssml_message, script)

    # Generate audio delivery message
    def thanks_for_listening(self, main: Article, first: Article, second: Article, third: Article) -> str:
        message = f"Happy listening! This article discusses {main.summary}. For further reads, check out {first.title} by {first.author} at {first.url}, {second.title} by {second.author} at {second.url}, or {third.title} by {third.author} at {third.url}. If you’d like to listen to any of these articles, run the tool again and type the title into search!"
        return self.generate(self.clean_message, message)
    
    # Create and deliver audio
    def audio_file(self, main: Article, first: Article, second: Article, third: Article, language: str) -> None:
        audio = gTTS(self.text_to_script(main, first, second, third), lang = "".join([key for key, value in self.supported_lang.items() if value == language]))
        title = f"{main.title}.mp3"
        audio.save(title)

if __name__ == '__main__':
    audicle = Audicle()
    audicle.main()