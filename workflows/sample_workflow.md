# 每日业务数据汇报

## Step 1: 抓取数据
- **Tools**: fetch_data
- **Dependencies**: 
- **Instruction**: 请调用抓取数据工具，获取今天最新的业务API指标数据。

## Step 2: 汇总并发送邮件
- **Tools**: send_email
- **Dependencies**: 抓取数据
- **Instruction**: 根据上一步抓取到的数据，生成一份简短的日报，并发送给管理员邮箱。