import requests
import time
import sys

# ==================== ⚙️ 配置区域 ====================

# 1. 🔴 请在这里填入你的 API Key (保留引号)
API_KEY = "fca50a131e18c871c838d4a6ec065be3"

# 2. 想要抓取多少？
# 建议设为 5 (即每年抓 100 部)，如果想要更多，可以改成 10 或 20
# 如果网速慢，建议保持在 5
MAX_PAGES_PER_YEAR = 5

# ==================== 🔧 固定配置 (不用改) ====================

OUTPUT_FILENAME = "new_movies_2013_2024_2.sql"
START_YEAR = 2013
END_YEAR = 2024

# 起始 ID (从 200,000 开始，绝对安全)
CURRENT_MOVIE_ID = 200000
CURRENT_PEOPLE_ID = 200000
people_cache = {}

# ==================== 🛠️ 核心函数 ====================

def get_json(url):
    """发送请求，带重试机制"""
    retries = 3
    for i in range(retries):
        try:
            # timeout=30 意味着如果30秒没反应才算超时，防止网慢报错
            response = requests.get(url, timeout=30)
            
            # 如果被限流 (429)，休息一下
            if response.status_code == 429:
                print("⚠️ 触发限流，等待 5 秒...")
                time.sleep(5)
                continue
                
            if response.status_code == 200:
                return response.json()
            
        except Exception as e:
            # 如果是最后一次尝试还失败，就打印错误
            if i == retries - 1:
                print(f"\n❌ 请求失败: {e}")
            time.sleep(2)
    return None

def clean_str(text):
    """清洗字符串，防止 SQL 报错"""
    if not text: return ""
    # 替换单引号 ' 为 ''，去掉反斜杠
    return str(text).replace("'", "''").replace("\\", "")

# ==================== 🚀 主程序 ====================

def main():
    global CURRENT_MOVIE_ID, CURRENT_PEOPLE_ID
    
    # 简单的检查 Key
    if "YOUR_TMDB" in API_KEY:
        print("❌ 错误：请先修改代码第 12 行，填入你的 API Key！")
        return

    print(f"🚀 开始抓取任务: {START_YEAR} - {END_YEAR} 年")
    print(f"📄 每年抓取 {MAX_PAGES_PER_YEAR} 页 (约 {MAX_PAGES_PER_YEAR * 20} 部电影)")
    print("⏳ 提示：如果没有开代理，速度可能会比较慢，请耐心等待...")

    with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
        # 写入文件头
        f.write("-- Auto-generated movie data (2013-2024)\n")
        f.write("-- Compatibility: PostgreSQL, openGauss\n")
        f.write("BEGIN;\n\n")

        for year in range(START_YEAR, END_YEAR + 1):
            print(f"\nProcessing Year: {year} ...")
            
            for page in range(1, MAX_PAGES_PER_YEAR + 1):
                # 打印进度 (不换行)
                sys.stdout.write(f"\r  -> 正在读取第 {page}/{MAX_PAGES_PER_YEAR} 页...")
                sys.stdout.flush()

                # 1. 获取电影列表
                discover_url = f"https://api.themoviedb.org/3/discover/movie?api_key={API_KEY}&primary_release_year={year}&sort_by=popularity.desc&page={page}"
                data = get_json(discover_url)
                
                if not data or 'results' not in data:
                    continue

                for m in data['results']:
                    tmdb_id = m['id']
                    title = clean_str(m.get('title', 'Unknown'))
                    
                    # 简单处理国家
                    lang = m.get('original_language', 'en')
                    country = lang[:2] if lang else 'us'
                    
                    # 默认时长 90 (为了节省一次 API 请求，不查详细信息了，速度翻倍)
                    runtime = 90
                    
                    # --- 写入 Movie ---
                    # Schema: INSERT INTO movies VALUES(movieid, title, country, year, runtime);
                    sql_movie = f"INSERT INTO movies VALUES({CURRENT_MOVIE_ID}, '{title}', '{country}', {year}, {runtime});\n"
                    f.write(sql_movie)
                    
                    # --- 获取演职员 (Credits) ---
                    credits_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/credits?api_key={API_KEY}"
                    cred = get_json(credits_url)
                    
                    if cred:
                        # 1. 处理导演
                        crew = cred.get('crew', [])
                        directors = [x for x in crew if x['job'] == 'Director']
                        if directors:
                            d = directors[0]
                            d_name = d['name']
                            
                            if d_name not in people_cache:
                                # 新增导演
                                parts = d_name.split(' ', 1)
                                first = clean_str(parts[0])
                                surname = clean_str(parts[1]) if len(parts) > 1 else ""
                                
                                # Schema: INSERT INTO people VALUES(id, first, surname, born, died, gender)
                                f.write(f"INSERT INTO people VALUES({CURRENT_PEOPLE_ID}, '{first}', '{surname}', NULL, NULL, 'M');\n")
                                people_cache[d_name] = CURRENT_PEOPLE_ID
                                d_id = CURRENT_PEOPLE_ID
                                CURRENT_PEOPLE_ID += 1
                            else:
                                d_id = people_cache[d_name]
                            
                            # 关联导演
                            f.write(f"INSERT INTO credits VALUES({CURRENT_MOVIE_ID}, {d_id}, 'D');\n")

                        # 2. 处理演员 (只取前 1 个，为了省空间)
                        cast = cred.get('cast', [])
                        if cast:
                            c = cast[0]
                            c_name = c['name']
                            
                            if c_name not in people_cache:
                                # 新增演员
                                parts = c_name.split(' ', 1)
                                first = clean_str(parts[0])
                                surname = clean_str(parts[1]) if len(parts) > 1 else ""
                                gender = 'F' if c.get('gender') == 1 else 'M'
                                
                                f.write(f"INSERT INTO people VALUES({CURRENT_PEOPLE_ID}, '{first}', '{surname}', NULL, NULL, '{gender}');\n")
                                people_cache[c_name] = CURRENT_PEOPLE_ID
                                c_id = CURRENT_PEOPLE_ID
                                CURRENT_PEOPLE_ID += 1
                            else:
                                c_id = people_cache[c_name]
                            
                            # 关联演员
                            f.write(f"INSERT INTO credits VALUES({CURRENT_MOVIE_ID}, {c_id}, 'A');\n")

                    CURRENT_MOVIE_ID += 1
                
                # 稍微休息一下
                time.sleep(0.1)

        f.write("\nCOMMIT;\n")
        print(f"\n\n✅ 任务完成！文件已生成: {OUTPUT_FILENAME}")

if __name__ == "__main__":
    main()