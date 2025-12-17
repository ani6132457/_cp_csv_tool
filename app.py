import streamlit as st
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="楽天CSV コピー生成", layout="wide")

st.title("楽天CSV コピー生成ツール")
st.caption("楽天CSVをアップロードすると、コピー用に必要な項目だけ変換してCSVを出力します（cp932）。")

# --------------------------
# 変換ロジック（今回確定版）
# --------------------------
def add_cp_if_not_blank(val):
    if pd.isna(val) or str(val).strip() == "":
        return val
    return f"{val}_cp"

def sku_insert_cp(val):
    if pd.isna(val) or str(val).strip() == "":
        return val
    s = str(val)
    # Xの直前に _cp を挿入（例: 7986559X11Y11 -> 7986559_cpX11Y11）
    return re.sub(r"^(.*?)(X.*)$", r"\1_cp\2", s)

def remove_rev_word(name):
    if pd.isna(name) or str(name).strip() == "":
        return name
    # 半角スペース区切りで ★REV から始まる単語を削除
    parts = str(name).split(" ")
    parts = [p for p in parts if not p.startswith("★REV")]
    return " ".join(parts)

def remove_rev_url(text):
    if pd.isna(text):
        return text
    # rev_ を含む画像URLだけ削除（他はそのまま）
    return re.sub(r"https?://[^\"'\s]*rev_[^\"'\s]*", "", str(text))

def transform(df: pd.DataFrame) -> pd.DataFrame:
    # 商品管理番号（商品URL） / 商品番号
    for c in ["商品管理番号（商品URL）", "商品番号"]:
        if c in df.columns:
            df[c] = df[c].apply(add_cp_if_not_blank)

    # 商品名
    if "商品名" in df.columns:
        df["商品名"] = df["商品名"].apply(remove_rev_word)

    # 説明文（rev_画像URL削除）
    for c in ["スマートフォン用商品説明文", "PC用販売説明文"]:
        if c in df.columns:
            df[c] = df[c].apply(remove_rev_url)

    # 商品画像パス1～20：rev_なら同番号のタイプ/ALTも空欄
    for i in range(1, 21):
        path_col = f"商品画像パス{i}"
        type_col = f"商品画像タイプ{i}"
        alt_col  = f"商品画像名（ALT）{i}"

        if path_col in df.columns:
            mask = df[path_col].astype(str).str.contains("rev_", na=False)
            df.loc[mask, path_col] = ""
            if type_col in df.columns:
                df.loc[mask, type_col] = ""
            if alt_col in df.columns:
                df.loc[mask, alt_col] = ""

    # SKU管理番号 / システム連携用SKU番号（Xの前に_cp、空白維持）
    for c in ["SKU管理番号", "システム連携用SKU番号"]:
        if c in df.columns:
            df[c] = df[c].apply(sku_insert_cp)

    return df

def to_cp932_bytes(df: pd.DataFrame) -> bytes:
    # 楽天互換でcp932にする
    return df.to_csv(index=False, encoding="cp932").encode("cp932", errors="replace")

# --------------------------
# UI
# --------------------------
files = st.file_uploader("楽天CSVを選択（複数可）", type=["csv"], accept_multiple_files=True)

col1, col2 = st.columns([1, 1])
with col1:
    run = st.button("変換してダウンロードファイルを作成", type="primary")

with col2:
    st.write("")

if files and run:
    st.success(f"{len(files)}ファイルを変換します。")

    for f in files:
        # cp932想定。ダメならutf-8も試す（楽天はほぼcp932）
        data = f.read()
        try:
            df = pd.read_csv(BytesIO(data), encoding="cp932")
        except UnicodeDecodeError:
            df = pd.read_csv(BytesIO(data), encoding="utf-8")

        out_df = transform(df)

        out_bytes = to_cp932_bytes(out_df)
        out_name = f"{f.name.rsplit('.', 1)[0]}_cp.csv"

        st.download_button(
            label=f"ダウンロード：{out_name}",
            data=out_bytes,
            file_name=out_name,
            mime="text/csv",
        )

elif files and not run:
    st.info("「変換してダウンロードファイルを作成」を押すと変換します。")
