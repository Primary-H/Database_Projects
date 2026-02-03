import requests
import time
import sys

# ==================== ⚙️ 配置区域 (请修改这里) ====================

# 1. 🔴 请把下面的 "你的_KEY_粘贴在这里" 替换为你第一步申请到的那串字符
# 注意：保留双引号，把 Key 放在引号中间
API_KEY = "fca50a131e18c871c838d4a6ec065be3" 

# 2. 想要抓取多少？
# 为了测试，建议先设为 5 (每页20部 x 5页 = 100部/年)
# 测试成功后，如果你想要“所有”电影，可以把这个数字改成 50 或 100
MAX_PAGES_PER_YEAR = 5

# ================================================================

OUTPUT_FILENAME = "new_movies_2013_2024.sql"
START_YEAR = 2013
END_YEAR = 2024

# 起始 ID (从 20万开始，避免和旧数据冲突)
CURRENT_MOVIE_ID = 200000
CURRENT_PEOPLE_ID = 200000
people_cache = {}

def get_json(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 429: # 如果请求太快被限流
            print("⚠️ 速度太快，休息 5 秒...")
            time.sleep(5)
            return get_json(url) # 重试
        if response.status_code != 200:
            return None
        return response.json()
    except:
        return None

def clean_str(text):
    """处理 SQL 中的单引号，防止报错"""
    if not text: return ""
    return str(text).replace("'", "''").replace("\\", "")

def main():
    global CURRENT_MOVIE_ID, CURRENT_PEOPLE_ID
    
    # 检查 Key 是否填了
    if "你的_KEY" in API_KEY:
        print("❌ 错误：你忘记填 API Key 了！请修改代码第 9 行。")
        return

    print(f"🚀 开始抓取 {START_YEAR} - {END_YEAR} 年的电影...")
    print(f"📄 每年抓取页数: {MAX_PAGES_PER_YEAR}")
    
    with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
        f.write("-- Auto-generated update for Project 2\n")
        f.write("BEGIN;\n\n")

        for year in range(START_YEAR, END_YEAR + 1):
            print(f"\n正在处理年份: {year} ...")
            
            for page in range(1, MAX_PAGES_PER_YEAR + 1):
                # 显示进度
                sys.stdout.write(f"\r  -> 正在读取第 {page} 页...")
                sys.stdout.flush()

                url = f"https://api.themoviedb.org/3/discover/movie?api_key={API_KEY}&primary_release_year={year}&sort_by=popularity.desc&page={page}"
                data = get_json(url)
                
                if not data or 'results' not in data: break
                
                for m in data['results']:
                    # 准备数据
                    title = clean_str(m.get('title', 'Unknown'))
                    lang = m.get('original_language', 'en')
                    country = lang if len(lang) == 2 else 'us' # 简化处理
                    runtime = 90 # 默认时长
                    
                    # 1. 写 Movie
                    f.write(f"INSERT INTO movies VALUES({CURRENT_MOVIE_ID}, '{title}', '{country}', {year}, {runtime});\n")
                    
                    # 2. 获取演职员 (为了更完整，这里多一次请求)
                    # 如果觉得慢，可以把下面这一段注释掉
                    tmdb_id = m['id']
                    credits_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/credits?api_key={API_KEY}"
                    cred = get_json(credits_url)
                    
                    if cred:
                        # 找导演
                        crew = cred.get('crew', [])
                        directors = [x for x in crew if x['job'] == 'Director']
                        if directors:
                            d_name = clean_str(directors[0]['name'])
                            # 如果是新导演，分配 ID
                            if d_name not in people_cache:
                                people_cache[d_name] = CURRENT_PEOPLE_ID
                                f.write(f"INSERT INTO people VALUES({CURRENT_PEOPLE_ID}, '{d_name.split()[0]}', '{d_name.split()[-1] if ' ' in d_name else ''}', NULL, NULL, 'M');\n")
                                CURRENT_PEOPLE_ID += 1
                            
                            # 关联
                            f.write(f"INSERT INTO credits VALUES({CURRENT_MOVIE_ID}, {people_cache[d_name]}, 'D');\n")

                    CURRENT_MOVIE_ID += 1
                
                # 稍微休息一下，防封号
                time.sleep(0.2)
        
        f.write("\nCOMMIT;\n")
        print(f"\n\n✅ 成功！文件已生成: {OUTPUT_FILENAME}")
        print(f"📂 请在左侧文件栏找到它。")

if __name__ == "__main__":
    main()