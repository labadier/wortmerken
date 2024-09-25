import unicodedata, Levenshtein
import sqlite3, numpy as np

def softmax(x, temperature=2.0):
    e_x = np.exp((x - np.max(x))/temperature)
    return e_x / e_x.sum()

def remove_accents(input_str):
    # Normalize the string to decompose accents into separate characters
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    # Filter out the combining diacritical marks
    only_ascii = "".join([char for char in nfkd_form if not unicodedata.combining(char)])
    return only_ascii

def check_response(text: str, truth: int, threshold: float = 0.2) -> bool:

    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM translations WHERE source_word_id = '{truth}'")

    rows = cursor.fetchall()
    conn.close()

    gt = [remove_accents(i[2].strip()) for i in rows]
    
    text = remove_accents(text.strip())
    if not len(text):
         return False
    
    return any(Levenshtein.distance(text.lower(), g.lower())/max(len(g), len(text)) <= threshold for g in gt)
    

def sample_word(user_id, db_filename, epsilon = 0.1) -> str:
    
        conn = sqlite3.connect(db_filename)
        cursor = conn.cursor()
    
        cursor.execute(f"SELECT * FROM german_items WHERE user_id = '{user_id}'")
        rows = cursor.fetchall()
        
        z = [i[4] for i in rows]
        z = softmax(-np.array(z)).tolist()
        print(z)
        if np.random.rand() < epsilon:
            index = np.random.choice(len(rows))
        else:
            index = np.random.choice(len(rows), p=z)
            
        cursor.execute(f"UPDATE german_items SET times_guessed = times_guessed + 1 WHERE id = ?", (rows[index][0],))
        conn.commit()
        conn.close()
        
        return rows[index][1], rows[index][3]
