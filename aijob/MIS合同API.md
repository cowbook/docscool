# GetHtDetail 接口文档

## 1. 接口基本信息

| 属性 | 值 |
|------|-----|
| **接口名称** | 获取沿海管道合同详情 |
| **服务地址** | `http://10.254.56.59:7002/Liems/webservice/getHtDetail` |
| **请求方式** | GET / POST |
| **认证方式** | HTTP Basic Auth |
| **返回格式** | application/json |

---

## 2. 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `htno` | String | 是 | 合同编号（如：`134702`） |

---

## 3. 认证信息

| 属性 | 值 |
|------|-----|
| 用户名 | 从 `HT_DETAIL_API_USERNAME` 环境变量读取 |
| 密码 | 从 `HT_DETAIL_API_PASSWORD` 环境变量读取 |

---

## 4. 返回字段

### 4.1 合同信息

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `HTSP_NO` | String | 合同编号 | 134702 |
| `HTSP_ID` | String | 合同主键 | CG-GK-B-2025-122 |
| `HTSP_NAM` | String | 合同名称 | 广东省沿海成品油管道惠州-汕头-揭阳段（A段）工程钢管采购合同 |
| `HYVEN_NO` | String | 供应商名称 | 北京巨龙钢管有限公司 |
| `WZHT_AMT` | String | 合同金额 | 156397813.48783 |
| `HTSP_STA` | String | 审批状态 | 归档 |
| `CBUSR_ID` | String | 承办人 | 陈艳霞 |
| `CBCST_NO` | String | 承办部门 | 物资采购部 |
| `HTLXL_NO` | String | 合同确定方式 | 公开招标 |
| `FSTUSR_DTM` | String | 承办日期 | 2025-09-18 15:03:28 |
| `HTLX_NO` | String | 合同类型 | - |
| `FPLX_TYP` | String | 发票类型 | 增值税专用发票 |
| `SL_AWT` | String | 税率 | 13%J3进项税 |
| `JJFS_TYP` | String | 计价方式 | 总价合同 |
| `CUR_NO` | String | 货币类型 | 人民币 |
| `QDRQ_DTM` | String | 签订日期 | 2025-09-25 |
| `ZBSQ_NO` | String | 招采申请审批单 | 2700BA25070003 |
| `HT_YEAR` | String | 合同年数 | 1 |
| `PRO_NO` | String | 项目名称 | 广东省沿海成品油管道惠州-汕头-揭阳段（A段）工程 |
| `JHRQ_DTM` | String | 交货日期 | 2025-11-30 |
| `payment` | Array | 付款信息列表 | [] |

### 4.2 付款信息（payment 数组）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `FPYZ_NAM` | String | 付款描述 |
| `VEN_NO` | String | 供应商名称 |
| `FKSP_STA` | String | 审批状态 |
| `FKLX_NO` | String | 付款类型 |
| `YSM_ID` | String | 预算码 |
| `FPYZ_AMT` | String | 合同金额 |
| `BCZF_AMT` | String | 本次支付金额 |
| `YHYZF_AMT` | String | 已支付金额 |
| `CWFK_ID` | String | 付款审批编号 |
| `JSFS_TYP` | String | 结算方式 |
| `FPYZ_NO` | String | 发票预制编号 |
| `YWLX_TYP` | String | 业务类型 |
| `CN_QTY` | String | 财年 |
| `JBUSR_ID` | String | 承办人 |
| `JBRQ_DTM` | String | 承办日期 |
| `JHFK_DTM` | String | 计划付款日期 |

---

## 5. 调用示例

### 5.1 curl

```bash
# GET 请求
curl -u "$HT_DETAIL_API_USERNAME:$HT_DETAIL_API_PASSWORD" "http://10.254.56.59:7002/Liems/webservice/getHtDetail?htno=134702"

# POST 请求
curl -u "$HT_DETAIL_API_USERNAME:$HT_DETAIL_API_PASSWORD" -X POST "http://10.254.56.59:7002/Liems/webservice/getHtDetail" -d "htno=134702"
```

### 5.2 Python

```python
import requests
import os

url = "http://10.254.56.59:7002/Liems/webservice/getHtDetail"
response = requests.get(
    url,
    params={"htno": "134702"},
    auth=(os.getenv("HT_DETAIL_API_USERNAME"), os.getenv("HT_DETAIL_API_PASSWORD")),
)
print(response.json())
```

### 5.3 JavaScript (fetch)

```javascript
fetch('http://10.254.56.59:7002/Liems/webservice/getHtDetail?htno=134702', {
    headers: { 'Authorization': 'Basic ' + btoa(`${HT_DETAIL_API_USERNAME}:${HT_DETAIL_API_PASSWORD}`) }
})
.then(res => res.json())
.then(data => console.log(data));
```

### 5.4 Java

```java
import java.net.*;
import java.io.*;
import java.util.Base64;

public class HtDetailClient {
    public static void main(String[] args) throws Exception {
        String url = "http://10.254.56.59:7002/Liems/webservice/getHtDetail?htno=134702";
        URL obj = new URL(url);
        
        String auth = System.getenv("HT_DETAIL_API_USERNAME") + ":" + System.getenv("HT_DETAIL_API_PASSWORD");
        String encodedAuth = Base64.getEncoder().encodeToString(auth.getBytes());
        
        HttpURLConnection con = (HttpURLConnection) obj.openConnection();
        con.setRequestMethod("GET");
        con.setRequestProperty("Authorization", "Basic " + encodedAuth);
        con.setRequestProperty("Accept", "application/json");
        
        BufferedReader in = new BufferedReader(new InputStreamReader(con.getInputStream()));
        String inputLine;
        StringBuffer response = new StringBuffer();
        
        while ((inputLine = in.readLine()) != null) {
            response.append(inputLine);
        }
        in.close();
        
        System.out.println(response.toString());
    }
}
```

---

## 6. 响应示例

```json
{
    "HTSP_NO": "134702",
    "HTSP_ID": "CG-GK-B-2025-122",
    "HTSP_NAM": "广东省沿海成品油管道惠州-汕头-揭阳段（A段）工程钢管采购合同",
    "HYVEN_NO": "北京巨龙钢管有限公司",
    "WZHT_AMT": "156397813.48783",
    "HTSP_STA": "归档",
    "CBUSR_ID": "陈艳霞",
    "CBCST_NO": "物资采购部",
    "HTLXL_NO": "公开招标",
    "FSTUSR_DTM": "2025-09-18 15:03:28.0",
    "HTLX_NO": "",
    "FPLX_TYP": "增值税专用发票",
    "SL_AWT": "13%J3进项税",
    "JJFS_TYP": "总价合同",
    "CUR_NO": "人民币",
    "QDRQ_DTM": "2025-09-25 00:00:00.0",
    "ZBSQ_NO": "2700BA25070003",
    "HT_YEAR": "1",
    "PRO_NO": "广东省沿海成品油管道惠州-汕头-揭阳段（A段）工程",
    "JHRQ_DTM": "2025-11-30 00:00:00.0",
    "payment": []
}
```

---

## 7. 状态码说明

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 401 | 未授权（缺少认证或认证失败） |
| 404 | 接口不存在 |

---

## 8. 注意事项

1. **合同编号**：传入 `htno` 参数（如 `134702`），合同主键
2. **认证**：必须携带 HTTP Basic Auth
3. **编码**：返回 UTF-8 编码
4. **付款信息**：`payment` 数组可能为空（如合同无付款记录）
5. **数据来源**：字段值通过 SQL 查询 `PJHTSPMST` 和 `PJCWFKMST` 表获取