import requests
import csv
import time
import os

# ==================== 配置区域 ====================
API_KEY = "fca50a131e18c871c838d4a6ec065be3"  # 🔴 替换为你的 TMDB Key
INPUT_CSV = "postgres_public_people.csv"     # DataGrip 导出的文件
OUTPUT_SQL = "fix_people_dates.sql" # 生成的补丁文件
# =================================================

def get_person_dates(first_name, surname):
    """
    搜索人物，返回 (born_year, died_year)
    """
    full_name = f"{first_name} {surname}".strip()
    try:
        # 1. 搜索人物 ID
        search_url = f"https://api.themoviedb.org/3/search/person?api_key={API_KEY}&query={full_name}"
        search_res = requests.get(search_url, timeout=5).json()
        
        if search_res.get('results'):
            # 取第一个最匹配的结果
            person_id = search_res['results'][0]['id']
            
            # 2. 获取详情 (为了得到 birthday 和 deathday)
            detail_url = f"https://api.themoviedb.org/3/person/{person_id}?api_key={API_KEY}"
            detail_res = requests.get(detail_url, timeout=5).json()
            
            # 3. 提取年份 (格式通常是 YYYY-MM-DD)
            b_date = detail_res.get('birthday')
            d_date = detail_res.get('deathday')
            
            b_year = int(b_date.split('-')[0]) if b_date else 0
            d_year = int(d_date.split('-')[0]) if d_date else 0
            
            return b_year, d_year
    except Exception as e:
        # print(f"  ❌ 查询失败: {e}")
        pass
    
    return 0, 0

def main():
    if not os.path.exists(INPUT_CSV):
        print(f"找不到 {INPUT_CSV}，请先从 DataGrip 导出！")
        return

    print("🚀 开始读取 CSV 并联网查询 (这可能需要几分钟)...")
    
    updates = []
    
    # 读取 CSV (假设没有表头，或者跳过表头)
    # 如果 DataGrip 导出带表头，请将 next(reader) 取消注释
    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        # next(reader) # 如果你的 CSV 第一行是 title, id 等单词，请取消注释这就话
        
        rows = list(reader)
        total = len(rows)
        
        for i, row in enumerate(rows):
            # 这里的索引取决于你 CSV 的列顺序，通常是 ID, First, Surname
            if len(row) < 3: continue
            
            pid = row[0]
            fname = row[1]
            sname = row[2]
            
            print(f"\r[{i+1}/{total}] 正在查询: {fname} {sname}...", end="")
            
            born, died = get_person_dates(fname, sname)
            
            # 只有当查到了有效的出生年 (不为0) 才更新
            if born != 0:
                # 存入格式: (ID, Born, Died)
                updates.append(f"({pid}, {born}, {died})")
            
            time.sleep(0.05) # 防止 API 速率限制

    # 生成极速 SQL
    if updates:
        print(f"\n✅ 查询完成，找到 {len(updates)} 条有效数据，正在生成 SQL...")
        with open(OUTPUT_SQL, 'w', encoding='utf-8') as f:
            f.write("-- 人员日期自动修复补丁\n")
            f.write("BEGIN;\n\n")
            
            # 使用 PostgreSQL 的超快批量更新语法
            f.write("UPDATE people AS p\n")
            f.write("SET born = v.new_born,\n")
            f.write("    died = v.new_died\n")
            f.write("FROM (VALUES\n")
            
            f.write(",\n".join(updates))
            
            f.write("\n) AS v(id, new_born, new_died)\n")
            f.write("WHERE p.peopleid = v.id;\n\n")
            
            f.write("COMMIT;\n")
            
        print(f"💾 文件已生成: {OUTPUT_SQL}")
        print("⚡ 请在 DataGrip 中右键运行此文件！")
    else:
        print("\n⚠️ 没有查到任何有效数据。")

if __name__ == "__main__":
    main()