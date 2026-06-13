r"""LDAP/AD Distinguished Name 解析工具，吸收各版本 AD 的格式落差。

各版本 Windows AD（2003~2025）OU 的 DN 結構一致，但實務上有三類落差會讓
裸字串處理出錯，這裡集中處理：

1. 大小寫：`OU=` 與 `ou=`、屬性名大小寫不保證一致 → 比對父子用正規化鍵。
2. 跳脫字元：RDN 值含 `,` `+` `=` `\` `#` `;` 時 DN 會跳脫成 `\,`，
   裸 `split(",")` 會被假逗號切錯 → 用尊重跳脫的 RDN 切割。
3. 取名：OU 短名優先取 `ou`/`name` 屬性，缺則取 DN 第一段 RDN 的值（已解跳脫）。
"""


def split_rdns(dn: str) -> list[str]:
    """把 DN 切成 RDN 串列，尊重反斜線跳脫（`\\,` 不視為分隔）。

    例：'OU=A\\,B,OU=工程部,DC=x' → ['OU=A\\,B', 'OU=工程部', 'DC=x']
    """
    rdns: list[str] = []
    cur: list[str] = []
    i = 0
    n = len(dn)
    while i < n:
        ch = dn[i]
        if ch == "\\" and i + 1 < n:
            # 跳脫序列：原樣保留兩字元
            cur.append(dn[i : i + 2])
            i += 2
            continue
        if ch == ",":
            rdns.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    if cur:
        rdns.append("".join(cur))
    return [r for r in rdns if r]


def parent_dn(dn: str) -> str:
    """父 DN = 去掉第一個 RDN（尊重跳脫）。頂層回空字串。"""
    rdns = split_rdns(dn)
    return ",".join(rdns[1:]) if len(rdns) > 1 else ""


def ou_depth(dn: str) -> int:
    """以 OU= 段數當深度（大小寫無關），父單位段數少、先處理。"""
    return sum(1 for r in split_rdns(dn) if r.strip().lower().startswith("ou="))


def normalize_dn(dn: str) -> str:
    """正規化 DN 作為大小寫無關的比對鍵。

    AD 的 DN 比對整體不分大小寫（屬性名與值皆然），故屬性名與值都轉小寫，
    並去除等號周圍與 RDN 間的多餘空白。回傳僅用於比對的鍵，**不回寫 AD**；
    原樣 DN 另存於 OrgUnit.external_id。
    """
    parts = []
    for rdn in split_rdns(dn):
        if "=" in rdn:
            attr, _, val = rdn.partition("=")
            parts.append(f"{attr.strip().lower()}={val.strip().lower()}")
        else:
            parts.append(rdn.strip().lower())
    return ",".join(parts)


def _unescape(value: str) -> str:
    """解 RDN 值的反斜線跳脫，取得可讀名稱。"""
    out: list[str] = []
    i = 0
    n = len(value)
    while i < n:
        if value[i] == "\\" and i + 1 < n:
            out.append(value[i + 1])
            i += 2
        else:
            out.append(value[i])
            i += 1
    return "".join(out)


def name_from_dn(dn: str) -> str:
    """從 DN 第一段 RDN 取值並解跳脫。'OU=後端課,...' → '後端課'。"""
    rdns = split_rdns(dn)
    if not rdns:
        return dn
    first = rdns[0]
    val = first.split("=", 1)[1] if "=" in first else first
    return _unescape(val.strip())
