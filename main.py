import logging
import os
import time
import openai
from plexapi.server import PlexServer
from utils.classes import UserInputs

userInputs = UserInputs(
    plex_url=os.getenv("PLEX_URL"),
    plex_token=os.getenv("PLEX_TOKEN"),
    openai_key=os.getenv("OPENAI_KEY"),
    tv_library_names=os.getenv("TV_LIBRARY_NAMES", "").split(","),
    movie_library_names=os.getenv("MOVIE_LIBRARY_NAMES", "").split(","),
    collection_title=os.getenv("COLLECTION_TITLE"),
    history_amount=int(os.getenv("HISTORY_AMOUNT")),
    recommended_amount=int(os.getenv("RECOMMENDED_AMOUNT")),
    minimum_amount=int(os.getenv("MINIMUM_AMOUNT")),
    wait_seconds=int(os.getenv("SECONDS_TO_WAIT", 43200)),
    openai_model=os.getenv("OPENAI_MODEL"),
)

logger = logging.getLogger()
logging.basicConfig(level=logging.INFO)

openai.api_key = userInputs.openai_key

def create_collection(plex, movie_items, description, library):
    logging.info("Finding matching movies in your library...")
    movie_list = []
    for item in movie_items:
        cleaned_item = re.sub(r"[^a-zA-Z0-9\s]", "", item).strip()
        movie_search = plex.search(cleaned_item, mediatype="movie", limit=3)
        if len(movie_search) > 0:
            movie_list.append(movie_search[0])
            logging.info(f"{cleaned_item} - found")
        else:
            logging.info(f"{cleaned_item} - not found")

    if len(movie_list) > userInputs.minimum_amount:
        try:
            collection = library.collection(userInputs.collection_title)
            collection.removeItems(collection.items())
            collection.addItems(movie_list)
            collection.editSummary(description)
            logging.info("Updated pre-existing collection")
        except:
            collection = plex.createCollection(
                title=userInputs.collection_title,
                section=library.title,
                items=movie_list
            )
            collection.editSummary(description)
            logging.info("Added new collection")
    else:
        logging.info("Not enough movies were found")

def run():
    # Connect
    while True:
        logger.info("Starting collection run")
        try:
            plex = PlexServer(userInputs.plex_url, userInputs.plex_token)
            logging.info("Connected to Plex server")
        except Exception as e:
            logging.error("Plex Authorization error")
            return

         for library_name in userInputs.library_names:
            try:
                # Fetch watch history from Plex
                library = plex.library.section(library_name.strip())
                account_id = plex.systemAccounts()[1].accountID

                # a = library.hubs()

                items_string = ""
                history_items_titles = []
                watch_history_items = plex.history(librarySectionID=library.key, maxresults=userInputs.history_amount, accountID=account_id)
                logging.info(f"Fetching items from your watch history in library {library_name.strip()}")

                for history_item in watch_history_items:
                    history_items_titles.append(history_item.title)

                items_string = ", ".join(history_items_titles)
                logging.info(f"Found {items_string} to base recommendations off")

            except Exception as e:
                logging.error(f"Failed to get watched items for library {library_name.strip()}")
                continue

            try:
                query = "Can you give me movie recommendations based on what I've watched? "
                query += "I've watched " + items_string + ". "
                query += "Can you base your recommendations solely on what I've watched already. "
                query += "I need around " + str(userInputs.recommended_amount) + ". "
                query += "Please give me the comma separated list, not a numbered list."

                logging.info("Querying openai for recommendations...")
                chat_completion = openai.ChatCompletion.create(model=openai_model, messages=[{"role": "user", "content": query}])
                movie_items = list(filter(None, chat_completion.choices[0].message.content.split(",")))
                logging.info("Query success!")
            except Exception as e:
                logging.error(f'Was unable to query openai: {e}')
                return

            if len(movie_items) > 0:
                create_collection(plex, movie_items, ai_movie_description, library)

            logging.info("Waiting on next call...")
            time.sleep(userInputs.wait_seconds)

if __name__ == '__main__':
    run()