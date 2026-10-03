import type { VNode } from 'vue'

/**
 * 通用表格的列定义。
 *
 * `render` 与具名插槽二选一：简单列（字符串、数字）直接给 `render`；
 * 需要在单元格里放链接、标签、折叠等结构时，用同名具名插槽
 * （`<template #列key="{ row }">`），模板里写结构比在 TS 里拼 VNode 清楚。
 */
export interface Column<Row> {
  /** 同时作为列标识与具名插槽名 */
  key: string
  header: string
  /** 数字列右对齐、等宽 */
  numeric?: boolean
  /** 该列的取值来源（数据源 / 口径），固定展示在表头小字里 */
  source?: string
  /** 简易取值；给了同名插槽时插槽优先 */
  render?: (row: Row, index: number) => string | number | null | undefined
}

/** 单元格渲染结果：空值统一显示「—」，不显示空白。 */
export type CellValue = string | number | null | undefined | VNode

export function cellText(value: CellValue): string {
  if (value === null || value === undefined || value === '') return '—'
  return String(value)
}
