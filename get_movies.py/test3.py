import requests
import time
import sys
import re
import os

# ==================== ⚙️ 配置区域 ====================

# 1. 🔴 请务必填入你的 TMDB API Key
API_KEY = "fca50a131e18c871c838d4a6ec065be3"

# 2. 抓取范围 (2018-2025)
START_YEAR = 2018
END_YEAR = 2025
MAX_PAGES_PER_YEAR = 50 

# 3. 文件名配置
EXISTING_DB_FILE = "filmdb.sql"
OUTPUT_FILENAME = "filmdb_staging_update.sql"

# ==================== 🧠 核心逻辑：读取老数据 ====================

existing_people_map = {}
max_people_id = 0
CURRENT_MOVIE_ID = 9205 
CURRENT_PEOPLE_ID = 20000 

def load_existing_data():
    """读取 filmdb.sql，建立人员去重索引"""
    global max_people_id, CURRENT_PEOPLE_ID
    print(f"📖 正在扫描 {EXISTING_DB_FILE} 建立人员索引...")
    
    if not os.path.exists(EXISTING_DB_FILE):
        print(f"⚠️ 警告: 找不到 {EXISTING_DB_FILE}！")
        return

    pattern = re.compile(r"INSERT INTO people VALUES\((\d+),\s*'([^']*)',\s*'([^']*)'", re.IGNORECASE)

    count = 0
    with open(EXISTING_DB_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            match = pattern.search(line)
            if match:
                pid = int(match.group(1))
                first = match.group(2).replace("''", "'").strip().lower()
                surname = match.group(3).replace("''", "'").strip().lower()
                
                if pid > max_people_id: max_people_id = pid
                existing_people_map[f"{first}|{surname}"] = pid
                count += 1
    
    if max_people_id >= CURRENT_PEOPLE_ID:
        CURRENT_PEOPLE_ID = max_people_id + 1
        
    print(f"✅ 索引建立完成！(新人物 ID 从 {CURRENT_PEOPLE_ID} 开始)")

# ==================== 🛠️ 辅助函数 ====================

def get_json(url):
    retries = 3
    for i in range(retries):
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 429:
                time.sleep(5)
                continue
            if response.status_code == 200:
                return response.json()
        except:
            time.sleep(1)
    return None

def clean_str(text):
    if not text: return ""
    return str(text).replace("'", "''").replace("\\", "").strip()

def get_country_logic(movie_item):
    origin = movie_item.get('origin_country', [])
    if origin: return origin[0].lower()[:2]
    mapping = {'en':'us', 'zh':'cn', 'cn':'cn', 'ja':'jp', 'ko':'kr'} # 简化的映射
    lang = movie_item.get('original_language', 'en').lower()
    return mapping.get(lang, 'us')

# ==================== 🚀 主程序 ====================

def main():
    global CURRENT_MOVIE_ID, CURRENT_PEOPLE_ID
    
    if "YOUR_TMDB" in API_KEY:
        print("❌ 错误：请先填入 API Key")
        return

    load_existing_data()
    new_people_cache = {} 

    print(f"🚀 开始抓取 (Staging 模式)...")

    with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
        # 1. 建表语句：注意 credits 表包含 credited_as 字段
        f.write("BEGIN;\n\n")
        f.write("CREATE TABLE new_movies_staging (movieid INT, title VARCHAR(255), country CHAR(2), year INT, runtime INT);\n")
        f.write("CREATE TABLE new_people_staging (peopleid INT, first_name VARCHAR(255), surname VARCHAR(255), born INT, died INT, gender CHAR(1));\n")
        f.write("CREATE TABLE new_credits_staging (movieid INT, peopleid INT, credited_as CHAR(1));\n\n")

        for year in range(START_YEAR, END_YEAR + 1):
            print(f"\nProcessing Year: {year} ...")
            
            for page in range(1, MAX_PAGES_PER_YEAR + 1):
                sys.stdout.write(f"\r  -> Page {page}/{MAX_PAGES_PER_YEAR} ...")
                sys.stdout.flush()

                url = f"https://api.themoviedb.org/3/discover/movie?api_key={API_KEY}&primary_release_year={year}&sort_by=popularity.desc&page={page}"
                data = get_json(url)
                if not data or 'results' not in data: break

                for m in data['results']:
                    try:
                        # --- 电影处理 ---
                        title = clean_str(m.get('title', 'Unknown'))
                        country = get_country_logic(m)
                        f.write(f"INSERT INTO new_movies_staging VALUES({CURRENT_MOVIE_ID}, '{title}', '{country}', {year}, 90);\n")
                        
                        # --- 职位处理核心逻辑 ---
                        cred_url = f"https://api.themoviedb.org/3/movie/{m['id']}/credits?api_key={API_KEY}"
                        cred = get_json(cred_url)
                        
                        if cred:
                            targets = []
                            # ✅ 1. 抓取导演 -> 标记为 'D'
                            dirs = [x for x in cred.get('crew', []) if x['job'] == 'Director']
                            if dirs: targets.append((dirs[0], 'D'))
                            
                            # ✅ 2. 抓取演员 -> 标记为 'A' (取前2位)
                            acts = cred.get('cast', [])[:2]
                            for a in acts: targets.append((a, 'A'))

                            for person, role in targets: # role 就是 'D' 或 'A'
                                p_name = person['name']
                                parts = p_name.split(' ', 1)
                                first = clean_str(parts[0])
                                surname = clean_str(parts[1]) if len(parts) > 1 else ""
                                search_key = f"{first.lower()}|{surname.lower()}"
                                
                                final_id = 0
                                # ID 判断逻辑
                                if search_key in new_people_cache:
                                    final_id = new_people_cache[search_key]
                                elif search_key in existing_people_map:
                                    final_id = existing_people_map[search_key]
                                else:
                                    final_id = CURRENT_PEOPLE_ID
                                    gender = 'F' if person.get('gender') == 1 else 'M'
                                    f.write(f"INSERT INTO new_people_staging VALUES({final_id}, '{first}', '{surname}', NULL, NULL, '{gender}');\n")
                                    new_people_cache[search_key] = final_id
                                    CURRENT_PEOPLE_ID += 1
                                
                                # ✅ 写入 Credits 表 (包含 credited_as 字段)
                                f.write(f"INSERT INTO new_credits_staging VALUES({CURRENT_MOVIE_ID}, {final_id}, '{role}');\n")

                    except Exception:
                        continue
                    CURRENT_MOVIE_ID += 1
                time.sleep(0.1)

        f.write("\nCOMMIT;\n")
        f.write("-- 验证后请执行以下合并语句:\n")
        f.write("-- INSERT INTO movies SELECT * FROM new_movies_staging;\n")
        f.write("-- INSERT INTO people SELECT * FROM new_people_staging;\n")
        f.write("-- INSERT INTO credits SELECT * FROM new_credits_staging;\n")

        print(f"\n✅ 任务完成！生成的 credits 记录已严格包含职位代码 (D/A)。")

if __name__ == "__main__":
    main()