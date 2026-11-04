# 百度云盘上传

分步引导完成百度云盘授权、依赖安装、选择本地文件、确认远端目录、上传并核验结果。

## 适用场景

- 将本地文件或文件夹上传到百度云盘
- 按日期、类别等规则保留目录结构
- 上传前确认文件范围和目标路径
- 上传后核对成功、失败和跳过的文件

## 首次配置

推荐使用百度网盘官方 `bdpan` 方案：

```bash
npx skills add https://github.com/baidu-netdisk/bdpan-storage/skills --skill baidu-drive
```

安装后检查：

```bash
command -v bdpan
bdpan --version
bdpan whoami
```

未登录时，必须使用官方 skill 目录中的登录脚本：

```bash
bash <官方 skill 目录>/scripts/login.sh
```

脚本会引导用户确认安全须知、打开百度 OAuth 授权链接、完成百度账号登录并输入授权码。不要在聊天中发送密码、token、cookie 或配置文件内容，也不要直接调用 `bdpan login`。

## 上传前后

上传前要确认实际本地文件、数量、类型、大小、远端完整目录、目录层级和同名文件策略；上传后必须核验任务完成或远端文件确实存在。仅返回 task id 或“已提交”不能称为上传成功。

默认不删除、不覆盖、不移动和不分享已有云盘文件。

详细执行规则见 [SKILL.md](SKILL.md)。

详细执行规则见 [SKILL.md](SKILL.md)。
