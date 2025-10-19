"""
このファイルは、最初の画面読み込み時にのみ実行される初期化処理が記述されたファイルです。
"""

############################################################
# ライブラリの読み込み
############################################################
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from uuid import uuid4
import sys
import unicodedata
from dotenv import load_dotenv
import streamlit as st
from docx import Document
from langchain_community.document_loaders import WebBaseLoader
from langchain_community.document_loaders import TextLoader
import pandas as pd
from langchain.docstore.document import Document
from langchain.text_splitter import CharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
import constants as ct


############################################################
# 設定関連
############################################################
# 「.env」ファイルで定義した環境変数の読み込み
load_dotenv()


############################################################
# 関数定義
############################################################

def initialize():
    """
    画面読み込み時に実行する初期化処理
    """
    # 初期化データの用意
    initialize_session_state()
    # ログ出力用にセッションIDを生成
    initialize_session_id()
    # ログ出力の設定
    initialize_logger()
    # RAGのRetrieverを作成
    initialize_retriever()


def initialize_logger():
    """
    ログ出力の設定
    """
    # 指定のログフォルダが存在すれば読み込み、存在しなければ新規作成
    os.makedirs(ct.LOG_DIR_PATH, exist_ok=True)
    
    # 引数に指定した名前のロガー（ログを記録するオブジェクト）を取得
    # 再度別の箇所で呼び出した場合、すでに同じ名前のロガーが存在していれば読み込む
    logger = logging.getLogger(ct.LOGGER_NAME)

    # すでにロガーにハンドラー（ログの出力先を制御するもの）が設定されている場合、同じログ出力が複数回行われないよう処理を中断する
    if logger.hasHandlers():
        return

    # 1日単位でログファイルの中身をリセットし、切り替える設定
    log_handler = TimedRotatingFileHandler(
        os.path.join(ct.LOG_DIR_PATH, ct.LOG_FILE),
        when="D",
        encoding="utf8"
    )
    # 出力するログメッセージのフォーマット定義
    # - 「levelname」: ログの重要度（INFO, WARNING, ERRORなど）
    # - 「asctime」: ログのタイムスタンプ（いつ記録されたか）
    # - 「lineno」: ログが出力されたファイルの行番号
    # - 「funcName」: ログが出力された関数名
    # - 「session_id」: セッションID（誰のアプリ操作か分かるように）
    # - 「message」: ログメッセージ
    formatter = logging.Formatter(
        f"[%(levelname)s] %(asctime)s line %(lineno)s, in %(funcName)s, session_id={st.session_state.session_id}: %(message)s"
    )

    # 定義したフォーマッターの適用
    log_handler.setFormatter(formatter)

    # ログレベルを「INFO」に設定
    logger.setLevel(logging.INFO)

    # 作成したハンドラー（ログ出力先を制御するオブジェクト）を、
    # ロガー（ログメッセージを実際に生成するオブジェクト）に追加してログ出力の最終設定
    logger.addHandler(log_handler)


def initialize_session_id():
    """
    セッションIDの作成
    """
    if "session_id" not in st.session_state:
        # ランダムな文字列（セッションID）を、ログ出力用に作成
        st.session_state.session_id = uuid4().hex


def initialize_retriever():
    """
    Retrieverの初期化
    """
    logger = logging.getLogger(ct.LOGGER_NAME)
    
    try:
        logger.info("=== Retriever初期化開始 ===")
        
        # OpenAI API キーの確認
        # .envファイルから再読み込みを確実に行う
        load_dotenv(override=True)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY が設定されていません")
            st.error("OpenAI API キーが設定されていません。.envファイルにOPENAI_API_KEYを設定してください。")
            return
        
        logger.info(f"OpenAI API キーが設定されています (長さ: {len(api_key)})")

        # RAGの参照先となるデータソースの読み込み
        logger.info("データソースの読み込みを開始します...")
        docs_all = load_data_sources()
        logger.info(f"読み込み完了: 総ドキュメント数 = {len(docs_all)}")
        
        # ドキュメントが空の場合の対処
        if not docs_all:
            logger.error("ドキュメントが読み込まれていません。data フォルダとファイルを確認してください。")
            st.error("ドキュメントの読み込みに失敗しました。data フォルダにファイルが存在するか確認してください。")
            return

        # OSがWindowsの場合、Unicode正規化と、cp932（Windows用の文字コード）で表現できない文字を除去
        for doc in docs_all:
            doc.page_content = adjust_string(doc.page_content)
            for key in doc.metadata:
                doc.metadata[key] = adjust_string(doc.metadata[key])
        
        # 埋め込みモデルの用意
        logger.info("OpenAI Embeddings を初期化しています...")
        try:
            embeddings = OpenAIEmbeddings()
            # テスト用の小さなテキストで埋め込み生成をテスト
            test_embedding = embeddings.embed_query("テスト")
            logger.info(f"埋め込みテスト成功: 次元数 = {len(test_embedding)}")
        except Exception as e:
            logger.error(f"OpenAI Embeddings の初期化に失敗: {str(e)}")
            st.error(f"OpenAI API の設定に問題があります: {str(e)}")
            return
        
        # チャンク分割用のオブジェクトを作成
        text_splitter = CharacterTextSplitter(
            chunk_size=ct.CHUNK_SIZE,
            chunk_overlap=ct.CHUNK_OVERLAP,
            separator="\n\n"  # txtファイルの論理的な分割のため、段落区切りを使用
        )

        # 部署別統合ドキュメントと通常ドキュメントを分離
        department_docs = [doc for doc in docs_all if doc.metadata.get("document_type") == "department_employees"]
        all_employees_docs = [doc for doc in docs_all if doc.metadata.get("document_type") == "all_employees"]
        regular_docs = [doc for doc in docs_all if doc.metadata.get("document_type") not in ["department_employees", "all_employees"]]
        
        logger.info(f"部署別統合ドキュメント: {len(department_docs)}件")
        logger.info(f"全社員統合ドキュメント: {len(all_employees_docs)}件")
        logger.info(f"通常ドキュメント: {len(regular_docs)}件")

        # 通常ドキュメントのみチャンク分割を実施
        splitted_regular_docs = text_splitter.split_documents(regular_docs)
        
        # 部署別統合ドキュメントと全社員統合ドキュメントはそのまま追加（分割しない）
        splitted_docs = splitted_regular_docs + department_docs + all_employees_docs
        
        logger.info(f"最終ドキュメント数: {len(splitted_docs)}件（分割後通常: {len(splitted_regular_docs)}, 統合: {len(department_docs + all_employees_docs)}）")

        # 最終的なドキュメント数の確認
        if not splitted_docs:
            logger.error("分割後のドキュメントが空です。ファイルの内容または形式に問題があります。")
            st.error("処理可能なドキュメントが見つかりませんでした。ファイルの内容を確認してください。")
            return
        
        logger.info(f"ベクトルストア作成開始: {len(splitted_docs)}件のドキュメントを処理します...")

        # ベクターストアの作成（エラーハンドリング付き）
        try:
            # 小さなバッチでテスト処理
            if len(splitted_docs) > 10:
                logger.info("大量のドキュメントのため、最初の10件でテスト処理を実行...")
                test_docs = splitted_docs[:10]
                test_db = Chroma.from_documents(test_docs, embedding=embeddings)
                logger.info("テスト処理成功、全体処理を開始...")
            
            # 全体のベクトルストア作成
            db = Chroma.from_documents(splitted_docs, embedding=embeddings)
            logger.info("ベクトルストア作成完了")
            
        except Exception as e:
            logger.error(f"ベクトルストア作成に失敗: {str(e)}")
            st.error(f"ベクトルストアの作成に失敗しました: {str(e)}")
            return

        # ベクターストアを検索するRetrieverの作成（検索パラメータを最適化）
        st.session_state.retriever = db.as_retriever(
            search_type="similarity", 
            search_kwargs={
                "k": ct.NUM_RETRIEVAL_DOCS
            }
        )
        
        logger.info("Retriever初期化完了")
        
    except Exception as e:
        logger.error(f"Retriever初期化エラー: {str(e)}")
        st.error(f"システム初期化に失敗しました: {str(e)}")
        raise e
    
    finally:
        # メモリクリーンアップ
        import gc
        gc.collect()


def initialize_session_state():
    """
    初期化データの用意
    """
    if "messages" not in st.session_state:
        # 「表示用」の会話ログを順次格納するリストを用意
        st.session_state.messages = []
        # 「LLMとのやりとり用」の会話ログを順次格納するリストを用意
        st.session_state.chat_history = []


def load_data_sources():
    """
    RAGの参照先となるデータソースの読み込み

    Returns:
        読み込んだ通常データソース
    """
    logger = logging.getLogger(ct.LOGGER_NAME)
    logger.info(f"データ読み込み開始: {ct.RAG_TOP_FOLDER_PATH}")
    
    # データフォルダの存在確認
    if not os.path.exists(ct.RAG_TOP_FOLDER_PATH):
        logger.error(f"データフォルダが見つかりません: {ct.RAG_TOP_FOLDER_PATH}")
        return []
    
    # データソースを格納する用のリスト
    docs_all = []
    # ファイル読み込みの実行（渡した各リストにデータが格納される）
    recursive_file_check(ct.RAG_TOP_FOLDER_PATH, docs_all)
    
    logger.info(f"ファイル読み込み完了: {len(docs_all)}件のドキュメント")

    web_docs_all = []
    # ファイルとは別に、指定のWebページ内のデータも読み込み
    # 読み込み対象のWebページ一覧に対して処理
    for web_url in ct.WEB_URL_LOAD_TARGETS:
        logger.info(f"Webページ読み込み: {web_url}")
        try:
            # 指定のWebページを読み込み
            loader = WebBaseLoader(web_url)
            web_docs = loader.load()
            # for文の外のリストに読み込んだデータソースを追加
            web_docs_all.extend(web_docs)
            logger.info(f"Webページ読み込み成功: {len(web_docs)}件")
        except Exception as e:
            logger.warning(f"Webページ読み込み失敗: {web_url} - {str(e)}")
    
    # 通常読み込みのデータソースにWebページのデータを追加
    docs_all.extend(web_docs_all)
    
    logger.info(f"総ドキュメント数: {len(docs_all)}件 (ファイル: {len(docs_all) - len(web_docs_all)}, Web: {len(web_docs_all)})")

    return docs_all


def recursive_file_check(path, docs_all):
    """
    RAGの参照先となるデータソースの読み込み

    Args:
        path: 読み込み対象のファイル/フォルダのパス
        docs_all: データソースを格納する用のリスト
    """
    # パスがフォルダかどうかを確認
    if os.path.isdir(path):
        # フォルダの場合、フォルダ内のファイル/フォルダ名の一覧を取得
        files = os.listdir(path)
        # 各ファイル/フォルダに対して処理
        for file in files:
            # ファイル/フォルダ名だけでなく、フルパスを取得
            full_path = os.path.join(path, file)
            # フルパスを渡し、再帰的にファイル読み込みの関数を実行
            recursive_file_check(full_path, docs_all)
    else:
        # パスがファイルの場合、ファイル読み込み
        file_load(path, docs_all)


def file_load(path, docs_all):
    """
    ファイル内のデータ読み込み

    Args:
        path: ファイルパス
        docs_all: データソースを格納する用のリスト
    """
    # ロガーを読み込む
    logger = logging.getLogger(ct.LOGGER_NAME)
    
    # ファイルの拡張子を取得
    file_extension = os.path.splitext(path)[1]
    # ファイル名（拡張子を含む）を取得
    file_name = os.path.basename(path)

    # 想定していたファイル形式の場合のみ読み込む
    if file_extension in ct.SUPPORTED_EXTENSIONS:
        try:
            # txtファイルの場合は文字エンコーディングの問題に対応
            if file_extension == ".txt":
                # まずUTF-8で試す
                try:
                    loader = TextLoader(path, encoding="utf-8")
                    docs = loader.load()
                except UnicodeDecodeError:
                    # UTF-8で失敗した場合はShift_JISで試す
                    try:
                        loader = TextLoader(path, encoding="shift_jis")
                        docs = loader.load()
                        logger.info(f"Shift_JISエンコーディングで読み込み: {path}")
                    except UnicodeDecodeError:
                        # それでも失敗した場合はcp932で試す
                        loader = TextLoader(path, encoding="cp932")
                        docs = loader.load()
                        logger.info(f"CP932エンコーディングで読み込み: {path}")
            elif file_extension == ".csv":
                # CSVファイルはカスタム処理
                docs = load_csv_with_department_grouping(path)
            else:
                # その他のファイルは通常通り処理
                loader = ct.SUPPORTED_EXTENSIONS[file_extension](path)
                docs = loader.load()
            
            docs_all.extend(docs)
            logger.info(f"ファイル読み込み成功: {path} (拡張子: {file_extension}, ドキュメント数: {len(docs)})")
        except Exception as e:
            logger.error(f"ファイル読み込み失敗: {path} - エラー: {str(e)}")
    else:
        logger.info(f"サポート外の拡張子のため読み込みスキップ: {path} (拡張子: {file_extension})")


def load_csv_with_department_grouping(path):
    """
    CSVファイルを部署別にグループ化して統合ドキュメントを作成
    """
    try:
        import pandas as pd
        from langchain.schema import Document
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"部署別CSV処理開始: {path}")
        
        # pandasでCSVを読み込み
        df = pd.read_csv(path, encoding="utf-8")
        logger.info(f"CSV読み込み完了: {len(df)}行")
        
        # 部署列の値を確認
        departments = df['部署'].unique()
        logger.info(f"検出された部署: {list(departments)}")
        
        documents = []
        
        # 部署ごとにドキュメントを作成
        for dept in departments:
            if pd.isna(dept):
                continue
                
            dept_employees = df[df['部署'] == dept]
            logger.info(f"部署別統合処理: {dept} - {len(dept_employees)}名")
            
            # 部署の統合ドキュメントを作成
            dept_content = f"【{dept}所属従業員一覧】\n\n"
            dept_content += f"部署名: {dept}\n"
            dept_content += f"所属従業員数: {len(dept_employees)}名\n\n"
            
            # 重要: 全員の個別情報を明確に区分して記載
            dept_content += f"=== 全{len(dept_employees)}名の個別詳細情報 ===\n\n"
            
            # 検索キーワードを冒頭に追加（検索精度向上のため）
            dept_content += f"検索対象: {dept}に所属している従業員情報 {dept}の従業員一覧 {dept}部門の社員リスト\n"
            dept_content += f"関連キーワード: {dept} {dept}所属 {dept}部門 {dept}スタッフ 従業員 社員 人員 メンバー 一覧 リスト 情報\n\n"
            
            # 人事部の場合は特別に強化
            if dept == "人事部":
                dept_content += f"人事部 人事部所属 人事部部門 人事課 人材管理部 HR部門 人事関連 人事担当 人事職員\n"
                dept_content += f"従業員一覧 社員一覧 スタッフ一覧 人員リスト 組織図 人事メンバー 人事チーム\n"
                dept_content += f"人事部に所属している従業員情報 人事部の従業員一覧 人事部門の社員 人事スタッフ情報\n"
                dept_content += f"※必ず{len(dept_employees)}名全員の情報を含む※\n\n"
                logger.info(f"人事部特別処理適用: {len(dept_employees)}名")
            
            # 従業員番号付きで詳細情報を記載
            for emp_num, (idx, employee) in enumerate(dept_employees.iterrows(), 1):
                dept_content += f"▼ {emp_num}番目の従業員情報:\n"
                employee_info = f"社員ID: {employee['社員ID']}\n"
                employee_info += f"氏名: {employee['氏名（フルネーム）']}\n"
                employee_info += f"性別: {employee['性別']}\n"
                employee_info += f"年齢: {employee['年齢']}\n"
                employee_info += f"部署: {employee['部署']}\n"
                employee_info += f"役職: {employee['役職']}\n"
                employee_info += f"従業員区分: {employee['従業員区分']}\n"
                if '入社日' in employee and pd.notna(employee['入社日']):
                    employee_info += f"入社日: {employee['入社日']}\n"
                if 'メールアドレス' in employee and pd.notna(employee['メールアドレス']):
                    employee_info += f"メールアドレス: {employee['メールアドレス']}\n"
                if 'スキルセット' in employee and pd.notna(employee['スキルセット']):
                    employee_info += f"スキルセット: {employee['スキルセット']}\n"
                if '保有資格' in employee and pd.notna(employee['保有資格']):
                    employee_info += f"保有資格: {employee['保有資格']}\n"
                
                dept_content += employee_info + "\n" + "-" * 50 + "\n\n"
            
            # 確認用情報を追加
            dept_content += f"\n=== {dept} 最終確認情報 ===\n"
            dept_content += f"この文書に含まれる{dept}の従業員数: {len(dept_employees)}名\n"
            dept_content += f"上記の{len(dept_employees)}名全員が{dept}所属の実在従業員です\n\n"
            
            # 検索キーワードを追加して検索精度を向上
            search_keywords = f"\n\n追加検索キーワード: {dept} {dept}所属 {dept}部門 {dept}の従業員 {dept}に所属している従業員"
            search_keywords += f" 従業員 社員 スタッフ 人事 営業 IT 総務 マーケティング 経理 一覧 リスト 情報 メンバー 人員"
            search_keywords += f" 組織 部署 チーム 職員 要員 人材"
            dept_content += search_keywords
            
            # 部署の統合ドキュメントを作成
            doc = Document(
                page_content=dept_content,
                metadata={
                    "source": path,
                    "department": dept,
                    "document_type": "department_employees",
                    "employee_count": len(dept_employees),
                    "search_keywords": f"{dept} 従業員 社員 一覧 リスト 所属 部門",
                    "title": f"{dept}所属従業員一覧",
                    "description": f"{dept}に所属している全従業員の詳細情報一覧"
                }
            )
            documents.append(doc)
            
            logger.info(f"部署別統合ドキュメント作成完了: {dept} ({len(dept_employees)}名)")
    
        # 全社員の統合ドキュメントも作成
        all_employees_content = "【全社員一覧】\n\n"
        for idx, employee in df.iterrows():
            employee_info = f"社員ID: {employee['社員ID']} | "
            employee_info += f"氏名: {employee['氏名（フルネーム）']} | "
            employee_info += f"部署: {employee['部署']} | "
            employee_info += f"役職: {employee['役職']} | "
            employee_info += f"従業員区分: {employee['従業員区分']}\n"
            all_employees_content += employee_info
        
        all_doc = Document(
            page_content=all_employees_content,
            metadata={
                "source": path,
                "document_type": "all_employees",
                "employee_count": len(df)
            }
        )
        documents.append(all_doc)
        
        logger.info(f"全社員統合ドキュメント作成完了: {len(df)}名")
        logger.info(f"CSV処理完了: 合計{len(documents)}ドキュメント作成")
        
        # 統合ドキュメントのみを返す（個別行ドキュメントは作成しない）
        return documents
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"CSV処理エラー: {path} - {str(e)}")
        # エラーの場合は従来のCSVLoaderを使用
        from langchain_community.document_loaders import CSVLoader
        loader = CSVLoader(path, encoding="utf-8")
        return loader.load()


def adjust_string(s):
    """
    Windows環境でRAGが正常動作するよう調整
    
    Args:
        s: 調整を行う文字列
    
    Returns:
        調整を行った文字列
    """
    # 調整対象は文字列のみ
    if type(s) is not str:
        return s

    # OSがWindowsの場合、Unicode正規化と、cp932（Windows用の文字コード）で表現できない文字を除去
    if sys.platform.startswith("win"):
        s = unicodedata.normalize('NFC', s)
        s = s.encode("cp932", "ignore").decode("cp932")
        return s
    
    # OSがWindows以外の場合はそのまま返す
    return s