from flask import Blueprint, request, jsonify, session, current_app
import pandas as pd
import numpy as np
import os
from app.data_utils import load_and_merge_csvs, filter_dataframe, convert_columns_to_numeric
from app.plot_utils import generate_scatter_plot

data_bp = Blueprint('data_bp', __name__)

@data_bp.route('/upload_csv', methods=['POST'])
def upload_csv():
    """
    CSVファイルをサーバーにアップロードし、ヘッダー情報を返します。
    Feature/Targetファイルパスとヘッダーはセッションに保存します。
    """
    file_type = request.form.get('file_type') # 'feature' or 'target'
    if not file_type or file_type not in ['feature', 'target']:
        return jsonify({'error': 'Invalid file type specified.'}), 400

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and file.filename.endswith('.csv'):
        filename = file.filename
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            df = pd.read_csv(filepath)
            headers = df.columns.tolist()
            # main_id を除外
            filtered_headers = [h for h in headers if h.lower() != 'main_id']

            # セッションにファイルパスとヘッダーを保存
            session[f'{file_type}_filepath'] = filepath
            session[f'{file_type}_headers'] = filtered_headers
            
            return jsonify({
                'filename': filename,
                'headers': filtered_headers,
                'filepath': filepath,
                'file_type': file_type
            }), 200
        except Exception as e:
            # ファイル読み込みエラーの場合は、セッション情報もクリアする
            session.pop(f'{file_type}_filepath', None)
            session.pop(f'{file_type}_headers', None)
            return jsonify({'error': f'Failed to read CSV or extract headers: {str(e)}'}), 500
    return jsonify({'error': 'Invalid file type'}), 400

@data_bp.route('/get_plot_data', methods=['POST'])
def get_plot_data():
    """
    フロントエンドからのパラメータ選択情報に基づいてPlotlyグラフデータを生成し返します。
    グラフ描画に使用するパラメータとデータの範囲をコンソールに出力します。
    """
    data = request.get_json()
    feature_params = data.get('featureParams', [])
    target_param = data.get('targetParam')

    feature_filepath = session.get('feature_filepath')
    target_filepath = session.get('target_filepath')

    if not feature_filepath or not target_filepath:
        return jsonify({'error': 'Feature or Target CSV file not uploaded.'}), 400

    try:
        df_merged = load_and_merge_csvs(feature_filepath, target_filepath)
        df_filtered = filter_dataframe(df_merged, feature_params)
        
        x_col = next((p['name'] for p in feature_params if p['type'] == 'X_axis'), None)
        y_col = next((p['name'] for p in feature_params if p['type'] == 'Y_axis'), None)
        z_col = target_param

        if not x_col or not y_col or not z_col:
            return jsonify({'error': 'Please select X-axis, Y-axis, and Target parameter.'}), 400
        
        if df_filtered.empty:
            return jsonify({'error': 'No data matches the selected constant filters.'}), 400

        if z_col not in df_filtered.columns:
            return jsonify({'error': f"Target parameter '{z_col}' not found in data."}), 400

        df_filtered = convert_columns_to_numeric(df_filtered, [x_col, y_col, z_col])
        df_filtered.dropna(subset=[x_col, y_col, z_col], inplace=True)

        if df_filtered.empty:
            return jsonify({'error': 'No valid numerical data after filtering and type conversion.'}), 400

        # --- ▼ここから変更▼ ---
        # グラフに表示するパラメータとその範囲/値をコンソールに出力
        current_app.logger.info("\n--- Plot Parameters and Data Range ---")
        
        # 補完点の数を変数として定義（後から変更しやすくするため）
        resolution = 10
        
        # Feature Parameters (X_axis, Y_axis, Constant)
        for param in feature_params:
            param_type = param.get('type')
            param_name = param.get('name')
            if param_type in ['X_axis', 'Y_axis']:
                min_val = df_filtered[param_name].min()
                max_val = df_filtered[param_name].max()
                
                # 最大値・最小値を表示
                current_app.logger.info(f'"{param_name}" ({param_type}): 最小値={min_val:.2f}, 最大値={max_val:.2f}')
                
                # 補完点の計算とフォーマット
                if min_val == max_val:
                    points_str = f"{min_val:.2f} (単一値)"
                else:
                    # np.linspaceで最小値と最大値の間を resolution 個の点で補完
                    points = np.linspace(min_val, max_val, resolution)
                    points_str = ", ".join([f"{p:.2f}" for p in points])
                
                # 補完点を表示
                current_app.logger.info(f'  - 補完点: [{points_str}]')

            elif param_type == 'Constant':
                current_app.logger.info(f'"{param_name}" (Constant): 設定値={param.get("value", "N/A")}')

        # Target Parameter
        if z_col in df_filtered.columns:
            min_val = df_filtered[z_col].min()
            max_val = df_filtered[z_col].max()
            current_app.logger.info(f'"{z_col}" (Target): 最小値={min_val:.2f}, 最大値={max_val:.2f}')
            
        current_app.logger.info("--------------------------------------\n")
        # --- ▲ここまで変更▲ ---

        graph_json, layout_json = generate_scatter_plot(df_filtered, x_col, y_col, z_col)
        
        return jsonify({'graph_json': graph_json, 'layout_json': layout_json}), 200

    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 400
    except KeyError as e:
        return jsonify({'error': f'Missing column in CSV: {str(e)}. Please check your CSV headers.'}), 400
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error in get_plot_data: {e}", exc_info=True)
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500

@data_bp.route('/get_model_table_headers', methods=['GET'])
def get_model_table_headers():
    """
    MODELタブのテーブル生成に必要なFeatureとTargetのヘッダーを返します。
    """
    feature_headers = session.get('feature_headers', [])
    target_headers = session.get('target_headers', [])

    # main_id を除外したヘッダーのみを返す
    filtered_feature_headers = [h for h in feature_headers if h.lower() != 'main_id']
    filtered_target_headers = [h for h in target_headers if h.lower() != 'main_id']

    if not filtered_feature_headers or not filtered_target_headers:
        return jsonify({'error': 'Feature or Target CSV headers not available. Please upload files.'}), 400

    return jsonify({
        'feature_headers': filtered_feature_headers,
        'target_headers': filtered_target_headers
    }), 200