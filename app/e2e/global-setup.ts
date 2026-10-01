import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))

/**
 * 在启动任何服务之前把环境恢复成确定状态。
 *
 * 两件事都必须做，否则端到端结果会依赖上一轮跑剩的状态：
 *   1. 重建数据库（表与数据）
 *   2. 清空端到端专用的缓存目录 —— 缓存是文件级的，上一轮的分析结果
 *      会被这一轮直接命中，断言就测不到「首次加载」的真实行为了
 */
export default function globalSetup(): void {
  const backendDir = path.resolve(here, '../../backend')
  const python = process.env.E2E_PYTHON || 'python'

  const cacheDir = path.resolve(backendDir, 'e2e-cache')
  fs.rmSync(cacheDir, { recursive: true, force: true })
  // 清空之后立刻把目录建回来：后端进程启动时已经 mkdir 过一次，
  // 若这里删掉而不重建，它之后每一笔缓存写入都会 ENOENT（CI 日志实证）。
  // 后端的 CacheManager 现在也会自愈，这里重建是为了语义正确（清空 ≠ 删除）。
  fs.mkdirSync(cacheDir, { recursive: true })

  execFileSync(python, ['scripts/dev_seed_sqlite.py', '--db', 'e2e.db'], {
    cwd: backendDir,
    stdio: 'inherit',
  })
}
