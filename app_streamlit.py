import io
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import re

# ページ設定
st.set_page_config(page_title="CSV Viewer", layout="wide")
st.title("Eddy CSV Plotter")

st.write("EddyHLで作成したCSVファイルをアップロードすると、時系列グラフとXYグラフで可視化できます")

# ファイルアップローダ
uploaded_file = st.file_uploader("CSVファイルを選択", type=["csv"])


# 🔍 数値判定（空文字・不可視文字・記号排除）
def is_number(s):
    s = str(s).strip()
    # 正の数 / 負の数 / 小数 を許可
    return bool(re.fullmatch(r"-?\d+(\.\d+)?", s))


# 🔍 ヘッダ行数を自動検出
def detect_data_start(head):
    """
    先頭の10行くらいを見て、
    「全セルが純粋な数値」の行をデータ開始とみなす。
    """
    for i in range(len(head)):
        row = head.iloc[i].dropna().astype(str)

        # 1セルでも非数値ならヘッダ扱い
        if len(row) == 0:
            continue

        if all(is_number(x) for x in row):
            return i

    return None


# 🔥 メインのCSV読み込み関数
def load_csv(file):
    """
    EddyHL形式のCSVを安全に読み込む。
    ・Shift-JIS対応
    ・ヘッダ行数が変動してもOK
    ・数値行自動検出で両フォーマットに完全対応
    """
    # まず先頭10行だけ読む（Shift-JIS前提）
    head = pd.read_csv(file, encoding="shift_jis", nrows=10, header=None)

    # データ開始行を推定
    data_start = detect_data_start(head)

    if data_start is None:
        raise ValueError("データ開始行を検出できませんでした（CSVフォーマット不明）")

    # 本番データの読み込み
    df = pd.read_csv(
        file,
        encoding="shift_jis",
        skiprows=data_start,
        header=None
    )

    # EddyHLは基本2列（Y, X）
    if df.shape[1] < 2:
        raise ValueError("データ列が2列未満です（壊れたCSVの可能性）")

    df = df.iloc[:, :2]
    df.columns = ["データY", "データX"]

    return df


if uploaded_file is not None:
    # ▼ 新しいファイルがアップロードされたら state 全部リセット（パターンA）
    file_id = (uploaded_file.name, uploaded_file.size)

    if st.session_state.get("last_file_id") != file_id:
        # いったん全部クリア
        st.session_state.clear()
        # 今回のファイル情報だけ保存し直す
        st.session_state["last_file_id"] = file_id

    try:
        df_data = load_csv(uploaded_file)

        st.success("CSV読み込み完了👌")

        # ========= 時系列グラフ =========
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


        # ========= XY 用インデックス範囲（スライダーのみ） =========

        max_idx = len(df_data) - 1

        # 再描画に実際使う範囲（ボタン押下時だけ更新）
        if "xy_range_applied" not in st.session_state:
            st.session_state["xy_range_applied"] = (0, max_idx)

        st.markdown("### XY 用インデックス範囲（スライダー）")

        # 今適用されている範囲をデフォルト値として使う
        applied_start, applied_end = st.session_state["xy_range_applied"]

        slider_start, slider_end = st.slider(
            "時系列グラフ上のインデックス範囲",
            min_value=0,
            max_value=max_idx,
            value=(int(applied_start), int(applied_end)),
            key="xy_slider",
        )

        # 再描画ボタン：押したときだけ適用
        # 適度な幅のカラム（中央寄せ）
        col_btn, _, _ = st.columns([1, 1, 1])

        with col_btn:
            redraw = st.button("XYグラフ再描画", use_container_width=True)


        if redraw:
            s = min(slider_start, slider_end)
            e = max(slider_start, slider_end)
            st.session_state["xy_range_applied"] = (s, e)

        # ここから下は「適用済みの範囲」を使ってXY描画
        s, e = st.session_state["xy_range_applied"]
        s = max(0, min(s, max_idx))
        e = max(0, min(e, max_idx))

        df_slice_full = df_data.iloc[s : e + 1]
        df_slice = df_slice_full.iloc[::10]    # 間引き（描画高速化）

        # 列名を特定（データY, データX を優先）
        try:
            y_col = "データY"
            x_col = "データX"
            _ = df_slice[[x_col, y_col]]  # 存在チェック
        except Exception:
            # 万一名前違っても、0列目→Y, 1列目→X とみなす
            y_col = df_slice.columns[0]
            x_col = df_slice.columns[1]

        # ========= XY 散布図 =========
        fig_xy = go.Figure()

        fig_xy.add_trace(
            go.Scattergl(
                x=df_slice[x_col],
                y=df_slice[y_col],
                mode="markers",
                marker=dict(size=3, opacity=0.1),
                name=f"{y_col} vs {x_col}",
            )
        )

        # x軸（-5〜5、1刻み、縦線見えるようにグリッド色指定）
        fig_xy.update_xaxes(
            title=x_col,
            range=[-5, 5],
            dtick=1,                  # グリッド間隔（1刻み）
            showgrid=True,            # グリッド線 ON
            gridcolor="#CCCCCC",      # 濃い目の灰色（見やすい）
            zeroline=True,
            zerolinecolor="#999999",
        )

        # y軸（-2.5〜2.5、0.5刻み → グリッド本数をxと合わせる）
        fig_xy.update_yaxes(
            title=y_col,
            range=[-2.5, 2.5],
            dtick=0.5,                # x と同数になるよう 0.5刻み
            showgrid=True,
            gridcolor="#CCCCCC",
            zeroline=True,
            zerolinecolor="#999999",
        )

        # 正方形で表示（縦横比 1:1）
        fig_xy.update_layout(
            width=600,
            height=600,
            margin=dict(l=50, r=20, t=40, b=40),
        )

        # XY は width="content" でPlotly側サイズをそのまま使う
        st.plotly_chart(fig_xy, width="content")

        # ▲▲▲ ここまで XY 散布図関連 ▲▲▲

    except Exception:
        st.error("読み込み失敗しました😂（CSVフォーマット or 文字コードを確認して）")

else:
    st.info("上のボックスからCSVをアップロードするとグラフ出ます📈")