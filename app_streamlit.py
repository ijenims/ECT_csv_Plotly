import io
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ページ設定
st.set_page_config(page_title="CSV Viewer", layout="wide")
st.title("Eddy CSV Plotter")

st.write("EddyHLで作成したCSVファイルをアップロードすると、時系列グラフとXYグラフで可視化できます")

# ファイルアップローダ
uploaded_file = st.file_uploader("CSVファイルを選択", type=["csv"])

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

        st.success("CSV読み込み完了👌")

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

        st.plotly_chart(fig, width="stretch")

        # ▼▼▼ ここから XY 用インデックス範囲のUI ▼▼▼

        # 使用可能なインデックス範囲
        max_idx = len(df_data) - 1

        # 「候補範囲」と「適用範囲」をセッションに保持
        if "xy_candidate" not in st.session_state:
            st.session_state["xy_candidate"] = (0, max_idx)  # スライダ＆手入力用
        if "xy_range" not in st.session_state:
            st.session_state["xy_range"] = (0, max_idx)      # 実際にXY描画に使う範囲

        cand_start, cand_end = st.session_state["xy_candidate"]

        st.markdown("### XY グラフ用インデックス範囲（スライダー）")

        # 時系列グラフの x 軸と同じ 0～max_idx を使う 2 ハンドルスライダー
        cand_start, cand_end = st.slider(
            "時系列グラフ上のインデックス範囲",
            min_value=0,
            max_value=max_idx,
            value=(int(cand_start), int(cand_end)),
            key="xy_slider",
        )

        # スライダーで動かした結果を候補範囲として保存
        st.session_state["xy_candidate"] = (int(cand_start), int(cand_end))

        st.markdown("---")
        st.subheader("XY グラフ（データX vs データY）")


        # いまの「候補範囲」を取得（スライダー or 手入力で編集される値）
        cand_start, cand_end = st.session_state["xy_candidate"]

        col1, col2, col3 = st.columns([1, 1, 1])

        with col1:
            start_idx = st.number_input(
                "開始インデックス (start)",
                min_value=0,
                max_value=max_idx,
                value=int(cand_start),
                step=1,
                key="xy_start",
            )

        with col2:
            end_idx = st.number_input(
                "終了インデックス (end)",
                min_value=0,
                max_value=max_idx,
                value=int(cand_end),
                step=1,
                key="xy_end",
            )

        with col3:
            redraw = st.button("XYグラフ再描画", use_container_width=True)

        # 手入力の内容で候補範囲を更新（スライダーと手入力のどっちで変えてもOK）
        cand_start = int(start_idx)
        cand_end = int(end_idx)
        st.session_state["xy_candidate"] = (cand_start, cand_end)

        # ボタンが押されたときだけ「適用範囲」を更新
        if redraw:
            s = int(min(cand_start, cand_end))
            e = int(max(cand_start, cand_end))
            st.session_state["xy_range"] = (s, e)


        # 実際に使うインデックス範囲
        s, e = st.session_state["xy_range"]

        # 範囲をクリップ（念のため）
        s = max(0, min(s, max_idx))
        e = max(0, min(e, max_idx))

        # 時系列で選んだ区間を切り出し（フル）
        df_slice_full = df_data.iloc[s : e + 1]

        # XY描画用に間引き（ここでは10点に1点）
        df_slice = df_slice_full.iloc[::10]


        # 列名を特定（データY, データX を優先）
        try:
            y_col = "データY"
            x_col = "データX"
            _ = df_slice[[x_col, y_col]]  # 存在チェック
        except Exception:
            # 万一名前違っても、0列目→Y, 1列目→X とみなす
            y_col = df_slice.columns[0]
            x_col = df_slice.columns[1]

        # XY散布図を作成
        # ---- XY 散布図 ----

        fig_xy = go.Figure()

        fig_xy.add_trace(
            go.Scattergl(
                x=df_slice[x_col],
                y=df_slice[y_col],
                mode="markers",
                marker=dict(size=3, opacity=0.1),
            )
        )

        # ▼ x軸
        fig_xy.update_xaxes(
            title=x_col,
            range=[-5, 5],
            dtick=1,                  # グリッド間隔（1刻み）
            showgrid=True,            # グリッド線 ON
            gridcolor="#CCCCCC",      # ← 濃い目の灰色（絶対見える）
            zeroline=True,
            zerolinecolor="#999999",
        )

        # ▼ y軸
        fig_xy.update_yaxes(
            title=y_col,
            range=[-2.5, 2.5],
            dtick=0.5,                # x と同数になるよう 0.5刻み
            showgrid=True,
            gridcolor="#CCCCCC",
            zeroline=True,
            zerolinecolor="#999999",
        )

        # ▼ 正方形で表示（縦横比1:1）
        fig_xy.update_layout(
            width=600,
            height=600,
            margin=dict(l=50, r=20, t=40, b=40),
        )

        # Plot
        st.plotly_chart(fig_xy, width="content")



        # ▲▲▲ ここまで XY 散布図関連 ▲▲▲


    except Exception:
        st.error("読み込み失敗しました😂（CSVフォーマット or 文字コードを確認して）")

else:
    st.info("上のボックスからCSVをアップロードするとグラフ出るで📈")
