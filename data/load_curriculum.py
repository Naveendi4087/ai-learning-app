import psycopg2
import os
import json
import glob
from dotenv import load_dotenv
from modules import db

# Run this script to populate the DB with Generic Curriculums
# python -m data.load_curriculum

def get_db_connection():
    load_dotenv()
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not found in .env file.")
        return None
    conn = psycopg2.connect(db_url)
    return conn

def load_course_from_json(cur, file_path):
    """
    Reads a JSON file and loads Knowledge Units and Topics for that subject.
    """
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return

    subject = data.get('subject')
    if not subject:
        print(f"Skipping {file_path}: No 'subject' field found.")
        return

    print(f"Processing Subject: {subject}...")

    # 1. Load Knowledge Units
    for ku in data.get('knowledge_units', []):
        cur.execute(
            "INSERT INTO knowledge_units (ku_code, ku_name, description) VALUES (%s, %s, %s) ON CONFLICT (ku_code) DO NOTHING",
            (ku['code'], ku['name'], ku['description'])
        )
    
    # 2. Load Topics
    for topic in data.get('topics', []):
        # Find the KU ID generic to the system
        cur.execute("SELECT id FROM knowledge_units WHERE ku_code = %s", (topic['ku_code'],))
        ku_row = cur.fetchone()
        
        if ku_row:
            ku_id = ku_row[0]
            cur.execute(
                """
                INSERT INTO topics (subject, ku_id, topic_name, topic_order) 
                VALUES (%s, %s, %s, %s) 
                ON CONFLICT (subject, topic_name) DO NOTHING
                """,
                (subject, ku_id, topic['name'], topic['order'])
            )
        else:
            print(f"  [WARN] KU Code {topic['ku_code']} not found for topic {topic['name']}")

    print(f"  -> {subject} Loaded successfully.")

def load_pedagogical_content(cur):
    print("Loading pedagogical content...")
    try:
        with open('data/pedagogical_content.json') as f:
            content_data = json.load(f)
    except FileNotFoundError:
        print("data/pedagogical_content.json not found. Skipping.")
        return
        
    for item in content_data:
        # We must now match Topic Name AND Subject
        subject = item.get('subject')
        topic_name = item.get('topic_name')

        if not subject: 
            print(f"Skipping content for {topic_name}: No 'subject' field in JSON.")
            continue

        cur.execute("SELECT id FROM topics WHERE topic_name = %s AND subject = %s", (topic_name, subject))
        topic_id_row = cur.fetchone()
        
        if not topic_id_row:
            print(f"  [SKIP] Content Topic '{topic_name}' ({subject}) not found in DB.")
            continue
            
        topic_id = topic_id_row[0]
        content = item['content']
        if isinstance(content, dict):
            content = json.dumps(content)
            
        cur.execute(
            """
            INSERT INTO pedagogical_content (topic_id, bloom_level, intention_type, content, author_notes)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (topic_id, bloom_level, intention_type) DO NOTHING
            """,
            (topic_id, item['bloom_level'], item['intention_type'], content, item.get('author_notes'))
        )
    print("Pedagogical content loaded.")

def load_question_bank(cur):
    print("Loading question bank...")
    try:
        with open('data/question_bank.json') as f:
            bank_data = json.load(f)
    except FileNotFoundError:
        print("data/question_bank.json not found. Skipping.")
        return
        
    for item in bank_data:
        subject = item.get('subject')
        topic_name = item.get('topic_name')

        if not subject:
            print(f"Skipping question for {topic_name}: No 'subject' field.")
            continue

        cur.execute("SELECT id FROM topics WHERE topic_name = %s AND subject = %s", (topic_name, subject))
        topic_id_row = cur.fetchone()
        
        if not topic_id_row:
            print(f"  [SKIP] Question Topic '{topic_name}' ({subject}) not found.")
            continue
            
        topic_id = topic_id_row[0]
        
        cur.execute(
            """
            INSERT INTO question_bank 
            (topic_id, question_text, options, correct_option_index, irt_difficulty_b, irt_discrimination_a, irt_guessing_c, test_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                topic_id,
                item['question_text'],
                json.dumps(item['options']),
                item['correct_option_index'],
                item['irt_difficulty_b'],
                item['irt_discrimination_a'],
                item['irt_guessing_c'],
                item['test_type']
            )
        )
    print("Question bank loaded.")

def main():
    conn = get_db_connection()
    if conn is None:
        return

    print("Attempting to create/update tables...")
    db.create_tables(conn)
    
    cur = conn.cursor()
    try:
        # 1. Load Curriculums from JSON files
        json_files = glob.glob("data/curriculums/*.json")
        if not json_files:
            print("No curriculum files found in data/curriculums/")
        
        for file_path in json_files:
            load_course_from_json(cur, file_path)

        # 2. Load Content & Questions (Now with Subject check)
        load_pedagogical_content(cur)
        load_question_bank(cur)
        
        conn.commit()
        print("\nDatabase population complete.")
    except Exception as e:
        conn.rollback()
        print(f"An error occurred: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()