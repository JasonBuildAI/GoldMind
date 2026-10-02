import type { ReactNode } from 'react'

export interface Column<Row> {
  key: string
  header: ReactNode
  /** 数字列右对齐、等宽 */
  numeric?: boolean
  /** 该列的取值来源（数据源 / 口径），固定展示在表头小字里 */
  source?: string
  render: (row: Row, index: number) => ReactNode
}

/**
 * 数字进表格的统一容器：所有数字表格从这里出，避免每个区块各写一套表结构。
 * 数字列由 numeric 统一右对齐（tabular-nums），来源列收在表头小字里。
 */
export default function DataTable<Row>({
  rows,
  columns,
  rowKey,
  caption,
  testId,
  empty,
}: {
  rows: Row[]
  columns: ReadonlyArray<Column<Row>>
  rowKey: (row: Row, index: number) => string
  caption?: ReactNode
  testId?: string
  /** 没有数据时的说明；给 undefined 表示不渲染表体 */
  empty?: ReactNode
}) {
  return (
    <div className="table-scroll">
      <table className="data-table" data-testid={testId}>
        {caption ? <caption className="note">{caption}</caption> : null}
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} scope="col" className={column.numeric ? 'num' : undefined}>
                {column.header}
                {column.source ? <span className="data-table__source">{column.source}</span> : null}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && empty !== undefined ? (
            <tr>
              <td colSpan={columns.length} className="note">
                {empty}
              </td>
            </tr>
          ) : null}
          {rows.map((row, index) => (
            <tr key={rowKey(row, index)}>
              {columns.map((column) => (
                <td key={column.key} className={column.numeric ? 'num' : undefined}>
                  {column.render(row, index)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}