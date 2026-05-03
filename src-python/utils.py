import unicodedata, Levenshtein
import sqlite3, numpy as np


def remove_accents(input_str):
    # Normalize the string to decompose accents into separate characters
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    # Filter out the combining diacritical marks
    only_ascii = "".join([char for char in nfkd_form if not unicodedata.combining(char)])
    return only_ascii

def check_response(text: str, 
                   truth: str, 
                   threshold: float = 0.2, 
                   file_db: str = "data") -> bool:

    conn = sqlite3.connect(file_db)
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM translations WHERE source_word_id = '{truth}'")

    rows = cursor.fetchall()
    conn.close()
    print(truth)
    gt = [remove_accents(i[2].strip()) for i in rows]
    
    text = remove_accents(text.strip())
    if not len(text):
         return False
    
    return any(Levenshtein.distance(text.lower(), g.lower())/max(len(g), len(text)) <= threshold for g in gt)
    

def sample_word(user_id, db_filename, epsilon = 0.05) -> str:

        conn = sqlite3.connect(db_filename)
        cursor = conn.cursor()

        # Active = not deactivated, Deactivated = flagged for exploration
        cursor.execute("SELECT id, word, times_guessed FROM german_items WHERE user_id = ? AND is_deactivated = 0", (user_id,))
        active_rows = cursor.fetchall()

        cursor.execute("SELECT id, word, times_guessed FROM german_items WHERE user_id = ? AND is_deactivated = 1", (user_id,))
        deactivated_rows = cursor.fetchall()

        if not active_rows and not deactivated_rows:
            conn.close()
            return None

        # Exploration picks from deactivated pool; exploitation prefers active
        r = np.random.rand()
        if r < epsilon and deactivated_rows:
            pool = deactivated_rows
        else:
            pool = active_rows if active_rows else deactivated_rows

        z = [i[2] for i in pool]

        # Keep previous heuristic: mostly pick the least 'times_guessed' item, with small randomization
        if np.random.rand() < epsilon:
            index = np.random.choice(len(pool))
        else:
            min_idxs = np.where(np.array(z) == min(z))[0]
            index = np.random.choice(min_idxs)

        chosen = pool[index]

        cursor.execute("UPDATE german_items SET times_guessed = times_guessed + 1 WHERE id = ?", (chosen[0],))
        cursor.execute("SELECT * FROM translations WHERE source_word_id = ?", (chosen[0],))

        tr = cursor.fetchone()
        hint = tr[2] if tr else ""

        conn.commit()
        conn.close()

        return chosen[1], hint + " "*np.random.randint(0, 10), chosen[0]
