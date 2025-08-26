# ====== 簡易パスワード認証 ======
PASSWORD = os.getenv("APP_PASSWORD", None) or st.secrets.get("auth", {}).get("password", "")

pw = st.text_input("Password", type="password")
if pw != PASSWORD:
    st.stop()  # パスワードが違ったらここで処理を止める
# ====== ここまで ======


import sqlite3
import random
import streamlit as st

DB_PATH = "lunch.db"

# ------------------------
# DBユーティリティ
# ------------------------

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS restaurants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            genre TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


# ------------------------
# データ操作
# ------------------------

def add_restaurant(name, genre, tags):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR IGNORE INTO restaurants(name, genre, tags)
        VALUES (?, ?, ?)
        """,
        (name.strip(), genre.strip(), tags.strip()),
    )
    conn.commit()
    conn.close()


def update_restaurant(rest_id, name, genre, tags, is_active):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE restaurants
        SET name=?, genre=?, tags=?, is_active=?
        WHERE id=?
        """,
        (
            name.strip(),
            genre.strip(),
            tags.strip(),
            1 if is_active else 0,
            int(rest_id),
        ),
    )
    conn.commit()
    conn.close()


def delete_restaurant(rest_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM restaurants WHERE id=?", (int(rest_id),))
    conn.commit()
    conn.close()


def list_restaurants(active_only=False, filters=None):
    conn = get_conn()
    cur = conn.cursor()
    base = "SELECT * FROM restaurants"
    conds = []
    params = []

    if active_only:
        conds.append("is_active=1")

    if filters:
        if kw := filters.get("keyword"):
            conds.append("(name LIKE ? OR tags LIKE ? OR genre LIKE ?)")
            params.extend([f"%{kw}%", f"%{kw}%", f"%{kw}%"]) 
        if tags := filters.get("tags"):
            for t in tags:
                conds.append("tags LIKE ?")
                params.append(f"%{t}%")
        if g := filters.get("genre"):
            conds.append("genre LIKE ?")
            params.append(f"%{g}%")

    if conds:
        base += " WHERE " + " AND ".join(conds)

    base += " ORDER BY name ASC"
    cur.execute(base, params)
    rows = cur.fetchall()
    conn.close()
    return rows


# ------------------------
# ランダム選出ロジック
# ------------------------

def choose_random(filtered_rows):
    if not filtered_rows:
        return None, "該当するお店がありません。フィルタを緩めてください。"

    pool = [row for row in filtered_rows if row["is_active"] == 1]
    if not pool:
        return None, "有効化されたお店がありません。管理タブで有効にしてください。"

    choice = random.choice(pool)
    return choice, None


# ------------------------
# UI
# ------------------------

st.set_page_config(page_title="今日のランチ決め", page_icon="🍱", layout="wide")

init_db()

st.title("今日のお昼何にします？")

with st.sidebar:
    st.header("フィルタ")
    kw = st.text_input("キーワード（店名・タグ・ジャンル）")
    selected_tags = st.text_input("タグで絞る（カンマ区切り）")

    # ジャンル一覧をDBから動的に取得
    all_genres = sorted({r["genre"] for r in list_restaurants(active_only=False, filters={}) if r["genre"]})
    genre_kw = st.selectbox("ジャンルで絞る", options=[""] + all_genres)

    filters = {
        "keyword": kw.strip() if kw else "",
        "tags": [t.strip() for t in selected_tags.split(",") if t.strip()] if selected_tags else [],
        "genre": genre_kw if genre_kw else None,
    }

pick_tab, manage_tab = st.tabs(["今日のランチ", "お店の管理"])

with pick_tab:
    st.subheader("🎯 今日のおすすめを決める")
    rows = list_restaurants(active_only=True, filters=filters)

    if st.button("ランダムに決める！", type="primary"):
        choice, err = choose_random(rows)
        if err:
            st.warning(err)
        else:
            st.success(f"今日のランチは **{choice['name']}** （ジャンル: {choice['genre']}）に決定！")

    st.divider()
    st.write("🔎 現在の候補一覧（フィルタ適用後）")
    if rows:
        st.dataframe(
            [{
                "店名": r["name"],
                "ジャンル": r["genre"],
                "タグ": r["tags"],
            } for r in rows],
            use_container_width=True,
        )
    else:
        st.info("条件に合うお店がありません。フィルタを緩めるか、管理タブからお店を追加してください。")

with manage_tab:
    st.subheader("🛠 お店の登録・編集")

    with st.expander("＋ 新規追加", expanded=True):
        with st.form("add_form"):
            name = st.text_input("店名")
            genre = st.text_input("ジャンル", placeholder="例：和食, 中華, イタリアン")
            tags = st.text_input("タグ（カンマ区切り）")
            submitted = st.form_submit_button("追加")
            if submitted:
                if not name.strip():
                    st.error("店名は必須です。")
                else:
                    add_restaurant(name, genre, tags)
                    st.success(f"{name} を追加しました。")

    st.divider()

    all_rows = list_restaurants(active_only=False, filters={})
    if all_rows:
        st.write("📋 登録済み一覧（クリックで編集）")
        for r in all_rows:
            with st.expander(f"{r['name']} (ID:{r['id']})"):
                with st.form(f"edit_{r['id']}"):
                    name_e = st.text_input("店名", value=r["name"])
                    genre_e = st.text_input("ジャンル", value=r["genre"])
                    tags_e = st.text_input("タグ", value=r["tags"])
                    active_e = st.checkbox("有効", value=bool(r["is_active"]))
                    col_a, col_b = st.columns(2)
                    with col_a:
                        save = st.form_submit_button("保存")
                    with col_b:
                        delete = st.form_submit_button("削除", type="secondary")

                    if save:
                        update_restaurant(r["id"], name_e, genre_e, tags_e, active_e)
                        st.success("保存しました。上のメニューで再読込してください。")
                    if delete:
                        delete_restaurant(r["id"])
                        st.warning("削除しました。上のメニューで再読込してください。")
    else:
        st.info("まだお店が登録されていません。上の『新規追加』から登録してください。")
