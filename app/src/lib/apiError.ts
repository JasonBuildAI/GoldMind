/**
 * 把接口错误翻译成**用户看得懂、也用得上**的一句话。
 *
 * 各区块原先各自写死两句：
 *
 *     setError('AI 分析耗时较长，请稍后重试刷新。');
 *     setError('获取最新分析失败。');
 *
 * 于是**任何**非超时的失败都显示「获取最新分析失败」—— 包括 429 限流。
 * 那既不准确（限流不是分析失败），也不可操作（没说等多久）。
 * 后端的 429 其实带了 `retry_after` 与 `Retry-After` 头，只是没人用。
 */

export interface ApiErrorLike {
  code?: string;
  message?: string;
  response?: {
    status?: number;
    headers?: Record<string, string>;
    data?: {
      error?: string;
      detail?: string;
      retry_after?: number;
    };
  };
}

export interface DescribeOptions {
  /** 兜底文案（认不出的错误用它）。 */
  fallback: string;
  /** 超时文案；不给就用兜底。 */
  timeout?: string;
}

export function describeApiError(err: unknown, options: DescribeOptions): string {
  const e = err as ApiErrorLike | undefined;
  const status = e?.response?.status;
  const data = e?.response?.data;

  // 1. 限流：说清「等多久」，而不是笼统的「失败」
  if (status === 429) {
    const wait =
      data?.retry_after ??
      Number(e?.response?.headers?.['retry-after'] ?? e?.response?.headers?.['Retry-After']);
    if (typeof wait === 'number' && Number.isFinite(wait) && wait > 0) {
      return `请求过于频繁，请 ${Math.ceil(wait)} 秒后重试。`;
    }
    return '请求过于频繁，请稍后重试。';
  }

  // 2. 服务端暂时不可用：优先用后端给的原因
  if (status === 503) {
    return data?.detail || data?.error || '后端暂时不可用，请稍后重试。';
  }

  // 3. 其余 4xx：后端有说明就用它的
  if (typeof status === 'number' && status >= 400 && status < 500) {
    return data?.detail || data?.error || options.fallback;
  }

  // 4. 超时 / 网络层失败
  const isTimeout =
    e?.code === 'ECONNABORTED' || (e?.message ?? '').toLowerCase().includes('timeout');
  if (isTimeout) {
    return options.timeout ?? options.fallback;
  }
  if (!e?.response) {
    return '无法连接后端，请检查网络后重试。';
  }

  return options.fallback;
}
