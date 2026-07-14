import zipfile
import json
import sqlite3
import pandas as pd
import os
import tempfile
from datetime import datetime
import streamlit as st

def process_zip(zip_file, custom_name, output_format):
    if not zip_file:
        return None, "Помилка: Файл не завантажено."
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    base_name = custom_name.strip() if custom_name and custom_name.strip() else "database"
    
    # Використовуємо тимчасовий файл
    temp_db_path = os.path.join(tempfile.gettempdir(), f"{base_name}_{date_str}.db")
    
    if os.path.exists(temp_db_path):
        try:
            os.remove(temp_db_path)
        except Exception:
            pass
            
    conn = sqlite3.connect(temp_db_path)
    report_lines = []
    total_records = 0
    
    # У Streamlit zip_file є BytesIO-подібним об'єктом
    with zipfile.ZipFile(zip_file, 'r') as z:
        json_files = [f for f in z.namelist() if f.endswith('.json')]
        
        if not json_files:
            return None, "В архіві не знайдено .json файлів."
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, filename in enumerate(json_files):
            status_text.text(f"Опрацювання: {filename}")
            with z.open(filename) as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    report_lines.append(f"❌ {filename}: Помилка читання JSON.")
                    continue
            
            if not data:
                report_lines.append(f"⚠️ {filename}: Порожній файл.")
                continue
            
            df = pd.DataFrame(data)
            
            for col in df.columns:
                if df[col].apply(lambda x: isinstance(x, (list, dict))).any():
                    df[col] = df[col].apply(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, (list, dict)) else x)
            
            table_name = "unknown"
            fname_lower = filename.lower()
            if "address" in fname_lower or "building" in fname_lower:
                table_name = "address"
            elif "street" in fname_lower:
                table_name = "street"
            elif "atu" in fname_lower:
                table_name = "atu"
            else:
                table_name = filename.split('.')[0]
                
            df.to_sql(table_name, conn, if_exists='append', index=False)
            records_count = len(df)
            total_records += records_count
            report_lines.append(f"✅ {filename} -> таблиця '{table_name}' ({records_count} записів).")
            
            progress_bar.progress((idx + 1) / len(json_files))
            
        status_text.empty()
        progress_bar.empty()

    if output_format == ".sql (PgAdmin)":
        sql_path = os.path.join(tempfile.gettempdir(), f"{base_name}_{date_str}.sql")
        with open(sql_path, 'w', encoding='utf-8') as f:
            for line in conn.iterdump():
                if not line.startswith('PRAGMA') and not line.startswith('BEGIN TRANSACTION'):
                    f.write(f"{line}\n")
        conn.close()
        final_file = sql_path
    else:
        conn.close()
        final_file = temp_db_path
        
    report_lines.append("-" * 30)
    report_lines.append(f"Всього опрацьовано файлів: {len(json_files)}")
    report_lines.append(f"Всього додано записів у базу: {total_records}")
    
    return final_file, "\n".join(report_lines)

# Інтерфейс Streamlit
st.set_page_config(page_title="JSON to Database Converter", layout="centered")
st.title("📂 Конвертер JSON (ZIP) у БД")

zip_input = st.file_uploader("Завантажити ZIP архів з JSON файлами", type=["zip"])
name_input = st.text_input("Бажана назва бази даних", placeholder="Наприклад: my_database")
format_input = st.radio(
    "Формат збереження",
    options=[".db (DBeaver / SQLite)", ".sql (PgAdmin)"]
)

if st.button("Опрацювати", type="primary"):
    if zip_input is not None:
        with st.spinner("Зачекайте, триває обробка..."):
            final_file_path, report = process_zip(zip_input, name_input, format_input)
            
            if final_file_path and os.path.exists(final_file_path):
                st.success("Обробку завершено успішно!")
                
                # Кнопка для завантаження файлу
                with open(final_file_path, "rb") as file:
                    st.download_button(
                        label="⬇️ Завантажити готовий файл",
                        data=file,
                        file_name=os.path.basename(final_file_path),
                        mime="application/octet-stream"
                    )
            
            st.text_area("Звіт про опрацювання", value=report, height=300)
    else:
        st.error("Будь ласка, завантажте ZIP-архів перед початком.")
