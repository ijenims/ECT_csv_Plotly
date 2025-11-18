import io
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ページ設定
st.set_page_config(page_title="2ch CSV Viewer", layout="wide")
st.title("2ch CSV Plotter（Streamlit版）")

st.write("CSVファイルをアップロードすると、2ch分の時系列データをPlotlyで可視化するで💅")

# ファイルアップローダ
uploaded_file = st.file_uploader("CSVファイルを選択してな〜", type=["csv"])

def load_csv(file) -> pd.DataFrame:
    """N23.csv 形式のCSVを確実に読むやつ（Shift-JIS対応）"""

    # 念のため先頭に戻す
    try:
        file.seek(0)
    except Exception:
        pass

    # バイト取得
    content = file.read()

    # 文字コード自動判定：UTF-8 → ダメなら Shift-JIS(cp932)
    for enc in ("utf-8-sig", "cp932", "utf-8"):
        try:
            text = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    lines = text.splitlines()

    # 3行目が「データY,データX」
    header_line = lines[2]
    col_names = [c.strip() for c in header_line.split(",") if c.strip()]

    # 4行目以降だけをデータとして読み込む
    data_text = "\n".join(lines[3:])

    df_data = pd.read_csv(
        io.StringIO(data_text),
        header=None,
        names=col_names,
    )

    # 数値に変換
    df_data = df_data.astype(float)

    return df_data


if uploaded_file is not None:
    try:
        # 読み込み
        df_data = load_csv(uploaded_file)

        st.success("CSV読み込み完了したで👌")

        # Plotlyで2ch重ね描画
        fig = go.Figure()

        for col in df_data.columns:
            fig.add_trace(
                go.Scatter(
                    y=df_data[col],
                    mode="lines",
                    name=col,
                )
            )

        fig.update_layout(
            xaxis_title="Index",   # サンプル番号
            yaxis_title="Value",   # 単位なし
            height=600,
        )

        st.plotly_chart(fig, use_container_width=True)

    except Exception:
        st.error("読み込み失敗しました😂（CSVフォーマット or 文字コードを確認してな〜）")

else:
    st.info("上のボックスからCSVをアップロードするとグラフ出るで📈")
