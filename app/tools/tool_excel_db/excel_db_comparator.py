"""
Excel与数据库数据比对工具

功能：
1. 读取Excel文件数据
2. 执行SQL查询获取数据库数据
3. 根据映射关系比对两边数据
4. 生成比对报告

作者: yandc
创建时间: 2026-02-06
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
from sqlalchemy import create_engine, text


class CompareResult(Enum):
    """比对结果类型"""
    MATCH = "match"           # 完全匹配
    MISMATCH = "mismatch"     # 值不匹配
    EXCEL_ONLY = "excel_only" # 仅Excel有
    DB_ONLY = "db_only"       # 仅数据库有


@dataclass
class FieldMapping:
    """字段映射配置"""
    excel_column: str      # Excel列名
    db_column: str         # 数据库列名
    is_key: bool = False   # 是否为主键（用于匹配行）
    compare: bool = True   # 是否参与比对


@dataclass
class CompareDetail:
    """单条记录比对详情"""
    key_values: Dict[str, Any]           # 主键值
    result: CompareResult                 # 比对结果
    differences: List[Dict[str, Any]] = field(default_factory=list)  # 差异详情


@dataclass
class CompareReport:
    """比对报告"""
    total_excel_rows: int = 0
    total_db_rows: int = 0
    matched_count: int = 0
    mismatched_count: int = 0
    excel_only_count: int = 0
    db_only_count: int = 0
    details: List[CompareDetail] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "summary": {
                "total_excel_rows": self.total_excel_rows,
                "total_db_rows": self.total_db_rows,
                "matched_count": self.matched_count,
                "mismatched_count": self.mismatched_count,
                "excel_only_count": self.excel_only_count,
                "db_only_count": self.db_only_count,
                "match_rate": f"{(self.matched_count / max(self.total_excel_rows, 1)) * 100:.2f}%"
            },
            "details": [
                {
                    "key_values": d.key_values,
                    "result": d.result.value,
                    "differences": d.differences
                }
                for d in self.details
            ]
        }


class ExcelDBComparator:
    """Excel与数据库比对器"""
    
    def __init__(self, db_uri: str):
        """
        初始化比对器
        
        Args:
            db_uri: 数据库连接URI
        """
        self.db_uri = db_uri
        self.engine = create_engine(db_uri)
    
    def read_excel(self, file_path: str, sheet_name: Optional[str] = None) -> pd.DataFrame:
        """
        读取Excel文件
        
        Args:
            file_path: Excel文件路径
            sheet_name: 工作表名称，默认读取第一个
            
        Returns:
            DataFrame数据
        """
        if sheet_name:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
        else:
            df = pd.read_excel(file_path)
        return df
    
    def execute_sql(self, sql: str) -> pd.DataFrame:
        """
        执行SQL查询
        
        Args:
            sql: SQL查询语句
            
        Returns:
            DataFrame数据
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(sql))
            columns = result.keys()
            rows = result.fetchall()
            return pd.DataFrame(rows, columns=columns)
    
    def parse_mappings(self, mapping_config: List[Dict[str, Any]]) -> List[FieldMapping]:
        """
        解析映射配置
        
        Args:
            mapping_config: 映射配置列表
            
        Returns:
            FieldMapping对象列表
        """
        mappings = []
        for config in mapping_config:
            mapping = FieldMapping(
                excel_column=config.get("excel_column"),
                db_column=config.get("db_column"),
                is_key=config.get("is_key", False),
                compare=config.get("compare", True)
            )
            mappings.append(mapping)
        return mappings
    
    def compare(
        self,
        excel_df: pd.DataFrame,
        db_df: pd.DataFrame,
        mappings: List[FieldMapping]
    ) -> CompareReport:
        """
        执行比对
        
        Args:
            excel_df: Excel数据
            db_df: 数据库数据
            mappings: 字段映射列表
            
        Returns:
            比对报告
        """
        report = CompareReport(
            total_excel_rows=len(excel_df),
            total_db_rows=len(db_df)
        )
        
        # 获取主键字段
        key_mappings = [m for m in mappings if m.is_key]
        compare_mappings = [m for m in mappings if m.compare and not m.is_key]
        
        if not key_mappings:
            raise ValueError("至少需要指定一个主键字段(is_key=true)")
        
        # 构建数据库数据索引（按主键）
        db_index = {}
        for _, row in db_df.iterrows():
            key = tuple(row[m.db_column] for m in key_mappings)
            db_index[key] = row
        
        # 记录已匹配的数据库记录
        matched_db_keys = set()
        
        # 遍历Excel数据进行比对
        for _, excel_row in excel_df.iterrows():
            key_values = {}
            excel_key = []
            
            for m in key_mappings:
                excel_val = excel_row.get(m.excel_column)
                key_values[m.excel_column] = self._convert_value(excel_val)
                excel_key.append(self._convert_value(excel_val))
            
            excel_key = tuple(excel_key)
            
            if excel_key in db_index:
                matched_db_keys.add(excel_key)
                db_row = db_index[excel_key]
                
                # 比对各字段
                differences = []
                for m in compare_mappings:
                    excel_val = self._convert_value(excel_row.get(m.excel_column))
                    db_val = self._convert_value(db_row.get(m.db_column))
                    
                    if not self._values_equal(excel_val, db_val):
                        differences.append({
                            "field": m.excel_column,
                            "excel_value": excel_val,
                            "db_value": db_val
                        })
                
                if differences:
                    report.mismatched_count += 1
                    report.details.append(CompareDetail(
                        key_values=key_values,
                        result=CompareResult.MISMATCH,
                        differences=differences
                    ))
                else:
                    report.matched_count += 1
                    report.details.append(CompareDetail(
                        key_values=key_values,
                        result=CompareResult.MATCH
                    ))
            else:
                report.excel_only_count += 1
                report.details.append(CompareDetail(
                    key_values=key_values,
                    result=CompareResult.EXCEL_ONLY
                ))
        
        # 检查仅数据库有的记录
        for db_key, db_row in db_index.items():
            if db_key not in matched_db_keys:
                key_values = {}
                for i, m in enumerate(key_mappings):
                    key_values[m.db_column] = self._convert_value(db_key[i])
                
                report.db_only_count += 1
                report.details.append(CompareDetail(
                    key_values=key_values,
                    result=CompareResult.DB_ONLY
                ))
        
        return report
    
    def _convert_value(self, value: Any) -> Any:
        """转换值为可比较的格式"""
        if pd.isna(value):
            return None
        if isinstance(value, (int, float)):
            # 处理浮点数精度问题
            if isinstance(value, float) and value.is_integer():
                return int(value)
            return value
        return str(value).strip()
    
    def _values_equal(self, val1: Any, val2: Any) -> bool:
        """比较两个值是否相等"""
        if val1 is None and val2 is None:
            return True
        if val1 is None or val2 is None:
            return False
        # 尝试数值比较
        try:
            return float(val1) == float(val2)
        except (ValueError, TypeError):
            return str(val1) == str(val2)
    
    def run_compare(
        self,
        excel_path: str,
        sql: str,
        mapping_config: List[Dict[str, Any]],
        sheet_name: Optional[str] = None
    ) -> CompareReport:
        """
        执行完整的比对流程
        
        Args:
            excel_path: Excel文件路径
            sql: SQL查询语句
            mapping_config: 映射配置
            sheet_name: Excel工作表名称
            
        Returns:
            比对报告
        """
        # 读取Excel
        excel_df = self.read_excel(excel_path, sheet_name)
        
        # 执行SQL
        db_df = self.execute_sql(sql)
        
        # 解析映射
        mappings = self.parse_mappings(mapping_config)
        
        # 执行比对
        return self.compare(excel_df, db_df, mappings)
