# Skill: Map Attributes & Build SQL Query

This skill maps attribute requirements from `attribute_list.csv` to actual database
columns in `drive_hd.csv`, then automatically generates a Trino SQL query.

## When to Use
Use this skill whenever the user wants to:
- ดึงข้อมูลจาก Drive RCA database โดยอิงจาก attribute list
- Map attribute names (ที่อาจไม่ตรง DB เป๊ะ) ไปยัง column จริงใน database
- สร้าง SQL query อัตโนมัติโดยไม่ต้องรู้ชื่อ column ใน DB
- ตรวจสอบว่า attribute ไหน match ได้หรือไม่ match

## Database Structure (Fixed JOIN Template)
Database: `iceberg.edputils` มี 3 tables:
- `v_drvsoftware_evt_hd_norm_date` (alias: **e**) — event header, normalized date
- `drvsoftware_rca_attr_pivot` (alias: **ap**) — attribute pivot table
- `drvsoftware_rca_attr_hd` (alias: **hd**) — attribute per head

Join keys:
- `e.drive_serial_num = ap.drive_serial_num AND e.event_date_key_st = ap.event_date_key`
- `e.drive_serial_num = hd.drive_serial_num AND e.event_date_key_st = hd.event_date_key AND e.head_no = hd.head_no`

## How to Execute
1. Call `map_and_fetch_data` tool with:
   - `threshold`: fuzzy match score (0–100), default 80
   - `time_filter`: optional SQL WHERE expression for date filtering
   - `limit`: row limit, default 1000
   - `select_all_event`: True to select e.* instead of only matched columns
2. The tool will:
   - Load `config/attribute_list.csv` + `config/drive_hd.csv`
   - Fuzzy-match each attribute → actual column name
   - Build the 3-table LEFT JOIN SQL
   - Execute query via Trino
   - Return mapping report + data preview
3. Show the user the mapping table (matched/unmatched)
4. Ask if they want to override any unmatched attributes before executing

## Handling Unmatched Attributes
- If attributes have status="unmatched" → inform the user with a clear list
- Suggest possible correct column names from the schema
- Allow user to manually specify the correct column via `override_mapping` parameter

## Example User Queries That Trigger This Skill
- "ดึงข้อมูลจาก attribute list"
- "Map attributes แล้ว query จาก Drive database"
- "สร้าง SQL จาก attribute_list.csv"
- "ดึงข้อมูล write error rate, read error rate สำหรับ RCA"
- "Build query from the requirements spec"
