# V01 — State coverage audit

Ngày kiểm tra: 2026-10-08
Nguồn: `fact_evaluated_loan` + `dim_state` trong `nghia.pbip`, truy vấn bằng Power BI Desktop MCP.
Population: **269.070 frozen-test evaluated loans**. `dim_state[country]` = `United States`.

## Kết luận

- Có **51 state/state-equivalent codes** có dữ liệu evaluated, gồm 50 bang và DC.
- Tổng số khoản vay theo state = **269.070**, khớp tổng evaluated population.
- Không có evaluated loan bị thiếu state trong relationship đang dùng cho V01.
- `IA` có 1 khoản vay, 0 default; đây là giá trị thật, không phải missing state. Measure riêng cho Map trả **0,00%** thay vì BLANK.
- Power BI tạo một blank referential member ngoài 51 state khi kiểm tra `VALUES(dim_state[state_code])`; member này có **0 evaluated loan** và không được coi là một state.
- Cột dùng để định vị là `dim_state[state_code]`, có data category `StateOrProvince`; country là `United States`. Không dùng ZIP, latitude hoặc longitude.

## Chi tiết theo state

| State | Evaluated Loan Count | Observed Default Count | Observed Default Rate | Recognized by map? |
|---|---:|---:|---:|---|
| AK | 674 | 136 | 20,18% | YES |
| AL | 3.422 | 809 | 23,64% | YES |
| AR | 1.990 | 457 | 22,96% | YES |
| AZ | 6.465 | 1.299 | 20,09% | YES |
| CA | 39.472 | 7.768 | 19,68% | YES |
| CO | 5.921 | 905 | 15,28% | YES |
| CT | 4.029 | 696 | 17,27% | YES |
| DC | 678 | 81 | 11,95% | YES |
| DE | 730 | 148 | 20,27% | YES |
| FL | 19.036 | 4.205 | 22,09% | YES |
| GA | 8.646 | 1.532 | 17,72% | YES |
| HI | 1.303 | 248 | 19,03% | YES |
| IA | 1 | 0 | 0,00% | YES |
| ID | 359 | 74 | 20,61% | YES |
| IL | 10.306 | 1.872 | 18,16% | YES |
| IN | 4.353 | 927 | 21,30% | YES |
| KS | 2.256 | 357 | 15,82% | YES |
| KY | 2.555 | 552 | 21,60% | YES |
| LA | 3.168 | 752 | 23,74% | YES |
| MA | 6.119 | 1.182 | 19,32% | YES |
| MD | 6.264 | 1.282 | 20,47% | YES |
| ME | 405 | 57 | 14,07% | YES |
| MI | 7.035 | 1.383 | 19,66% | YES |
| MN | 4.906 | 964 | 19,65% | YES |
| MO | 4.166 | 899 | 21,58% | YES |
| MS | 1.325 | 329 | 24,83% | YES |
| MT | 759 | 142 | 18,71% | YES |
| NC | 7.615 | 1.564 | 20,54% | YES |
| ND | 307 | 68 | 22,15% | YES |
| NE | 736 | 178 | 24,18% | YES |
| NH | 1.241 | 179 | 14,42% | YES |
| NJ | 9.790 | 2.073 | 21,17% | YES |
| NM | 1.465 | 332 | 22,66% | YES |
| NV | 4.134 | 877 | 21,21% | YES |
| NY | 21.710 | 4.804 | 22,13% | YES |
| OH | 8.757 | 1.838 | 20,99% | YES |
| OK | 2.473 | 579 | 23,41% | YES |
| OR | 3.285 | 441 | 13,42% | YES |
| PA | 9.103 | 1.843 | 20,25% | YES |
| RI | 1.211 | 202 | 16,68% | YES |
| SC | 3.178 | 540 | 16,99% | YES |
| SD | 545 | 113 | 20,73% | YES |
| TN | 4.051 | 876 | 21,62% | YES |
| TX | 22.176 | 4.437 | 20,01% | YES |
| UT | 1.993 | 339 | 17,01% | YES |
| VA | 7.583 | 1.534 | 20,23% | YES |
| VT | 528 | 75 | 14,20% | YES |
| WA | 5.773 | 874 | 15,14% | YES |
| WI | 3.492 | 639 | 18,30% | YES |
| WV | 1.002 | 152 | 15,17% | YES |
| WY | 579 | 107 | 18,48% | YES |

## Interpretation of the old colors

The old V01 was a **Shape map**, not a bubble Map. It bound evaluated count to the shape-map `Value` role while using a conditional fill based on the general `Observed Default Rate` measure. That could only color state shapes; it could not encode count as bubble size. The old fill rule also treated null as zero (`asZero`). Because the general rate measure returned BLANK for IA's zero-default group, that state was not being represented with a measured percentage. The old blue/gray appearance cannot be interpreted as a real risk value from the data; static PBIR and data audit do not show a data-backed blue category or an unrecognized evaluated state.

The repaired visual is a native **Map** with a bubble Size binding, sequential data-driven color, a zero-safe state-map rate measure, and explicit tooltips. Final visual rendering still requires checking the Map permission and the Desktop canvas.
