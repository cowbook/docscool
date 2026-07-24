<template>
  <div class="preview-page">
    <section class="left-pane">
      <div class="pane-title">PDF预览</div>
      <iframe
        v-if="!pdfPreviewLoading && effectivePdfPreviewUrl"
        class="pdf-frame"
        :src="effectivePdfPreviewUrl"
        title="PDF预览"
      />
      <div v-else class="pdf-placeholder">{{ pdfPreviewLoading ? '加载中...' : '暂无可预览PDF' }}</div>
    </section>

    <section class="right-pane">
      <div class="toolbar">
        <div class="toolbar-left">
          <button
            type="button"
            class="standalone-btn ai-btn"
            :disabled="aiRecognizing || !storagePdfPath"
            @click="runAiRecognition"
          >
            <span v-if="aiRecognizing" class="btn-spinner" aria-hidden="true"></span>
            <span v-else class="btn-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 3v4" />
                <path d="M12 17v4" />
                <path d="M3 12h4" />
                <path d="M17 12h4" />
                <path d="m5.6 5.6 2.8 2.8" />
                <path d="m15.6 15.6 2.8 2.8" />
                <path d="m18.4 5.6-2.8 2.8" />
                <path d="m8.4 15.6-2.8 2.8" />
              </svg>
            </span>
            <span>{{ aiRecognizing ? '识别中...' : (markdownExists ? '重新AI识别' : 'AI识别') }}</span>
          </button>

          <div class="toolbar-group-buttons" role="group" aria-label="编辑操作">

            <button
              type="button"
              class="group-btn state-btn"
              :class="editing ? 'is-editing' : 'is-viewing'"
              :disabled="!editing && !markdownExists"
              @click="toggleEditMode"
            >
              <span class="btn-icon" aria-hidden="true">
                <svg v-if="editing" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
                <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="m3 21 2.8-.6a2 2 0 0 0 1-.54L19.2 7.4a2.5 2.5 0 0 0 0-3.5 2.5 2.5 0 0 0-3.5 0L3.2 16.3a2 2 0 0 0-.54 1L2 20.9" />
                  <path d="m13.8 5.8 4.4 4.4" />
                </svg>
              </span>
              <span>{{ editing ? '切换到查看' : '进入编辑' }}</span>
            </button>

            <button
              type="button"
              class="group-btn save-btn"
              :disabled="!editing || saving"
              @click="saveMarkdown"
            >
              <span class="btn-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M5 3h12l4 4v14H3V3h2Z" />
                  <path d="M7 3v6h10V3" />
                  <path d="M8 16h8" />
                </svg>
              </span>
              <span>{{ saving ? '保存中...' : '保存' }}</span>
            </button>
          </div>
        </div>
        <div class="toolbar-status">{{ statusText }}</div>
      </div>

      <div v-show="!editing" class="markdown-view-wrap">
        <div class="markdown-scroll">
          <article class="markdown-body" v-html="viewHtml" />
        </div>
      </div>

      <div v-show="editing" class="editor-host">
        <div ref="toastEditorHost" class="toast-editor-host" />
      </div>
    </section>

  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import MarkdownIt from 'markdown-it'
import Editor from '@toast-ui/editor'
import '@toast-ui/editor/dist/toastui-editor.css'

const route = useRoute()
const md = new MarkdownIt({
  html: true,
  linkify: true,
  breaks: true,
})

const apiPrefix = import.meta.env.PROD ? '/docs/api' : '/api'

const loading = ref(false)
const saving = ref(false)
const editing = ref(false)
const aiRecognizing = ref(false)
const statusText = ref('加载中...')
const pdfPreviewUrl = ref('')
const pdfPreviewBlobUrl = ref('')
const pdfPreviewLoading = ref(false)
const markdownExists = ref(false)
const viewHtml = ref('')
const draftMarkdown = ref('')
const toastEditorHost = ref(null)
const toastEditor = ref(null)

const originalMarkdown = ref('')
const currentMarkdown = ref('')

const resolveMarkdownRelativePath = (rawPath) => {
  const normalized = String(rawPath || '').trim().replace(/^\/+/, '').replace(/\\/g, '/')
  if (!normalized) {
    return ''
  }

  if (normalized.toLowerCase().endsWith('.md')) {
    return normalized
  }

  return `${normalized.replace(/\/+$/, '')}/full.md`
}

const mdRelativePath = computed(() => {
  const rawParam = route.params?.ocrPath
  const paramPath = Array.isArray(rawParam) ? rawParam.join('/') : String(rawParam || '').trim()
  if (paramPath) {
    return resolveMarkdownRelativePath(paramPath)
  }

  const rawQuery = String(route.query.path || '').trim()
  return resolveMarkdownRelativePath(rawQuery)
})

const storagePdfPath = computed(() => {
  const path = String(mdRelativePath.value || '').trim()
  if (!path) {
    return ''
  }

  const normalized = path.replace(/\\/g, '/').replace(/^\/+/, '')
  const lower = normalized.toLowerCase()
  if (!lower.endsWith('/full.md') && lower !== 'full.md') {
    return ''
  }

  const dir = normalized.replace(/\/full\.md$/i, '')
  const parts = dir.split('/').filter(Boolean)
  const last = parts[parts.length - 1] || ''
  if (!last) {
    return ''
  }

  const parent = parts.slice(0, -1).join('/')
  return parent ? `${parent}/${last}.pdf` : `${last}.pdf`
})

const encodedMdPath = computed(() => {
  if (!mdRelativePath.value) {
    return ''
  }
  return mdRelativePath.value
    .split('/')
    .filter(Boolean)
    .map((item) => encodeURIComponent(item))
    .join('/')
})

const markdownApiUrl = computed(() => {
  if (!encodedMdPath.value) {
    return ''
  }
  return `${apiPrefix}/html/${encodedMdPath.value}`
})

const imageUploadApiUrl = computed(() => {
  if (!encodedMdPath.value) {
    return ''
  }
  return `${apiPrefix}/html-upload-image/${encodedMdPath.value}`
})

const markdownMetaApiUrl = computed(() => {
  if (!encodedMdPath.value) {
    return ''
  }
  return `${apiPrefix}/html-meta/${encodedMdPath.value}`
})

const normalizePreviewUrl = (rawUrl) => {
  const source = String(rawUrl || '').trim()
  if (!source) {
    return ''
  }

  if (import.meta.env.PROD) {
    if (source.startsWith('/api/')) {
      return `/docs${source}`
    }
    if (source.startsWith('/api?')) {
      return `/docs${source}`
    }
  } else {
    if (source.startsWith('/docs/api/')) {
      return source.replace(/^\/docs/, '')
    }
    if (source.startsWith('/docs/api?')) {
      return source.replace(/^\/docs/, '')
    }
  }

  return source
}

const storagePdfPreviewApiUrl = computed(() => {
  const path = String(storagePdfPath.value || '').trim()
  if (!path) {
    return ''
  }

  const encodedPath = path
    .split('/')
    .filter(Boolean)
    .map((item) => encodeURIComponent(item))
    .join('/')

  return `${apiPrefix}/folders/file-preview?path=${encodedPath}`
})

const isProtectedPdfPreviewUrl = (url) => {
  const source = String(url || '').trim()
  return source.startsWith('/api/folders/file-preview') || source.startsWith('/docs/api/folders/file-preview')
}

const effectivePdfPreviewUrl = computed(() => {
  if (pdfPreviewBlobUrl.value) {
    return pdfPreviewBlobUrl.value
  }

  if (isProtectedPdfPreviewUrl(pdfPreviewUrl.value)) {
    // Protected preview must be loaded via authorized blob first.
    return ''
  }

  return pdfPreviewUrl.value
})

const revokePdfBlobUrl = () => {
  if (pdfPreviewBlobUrl.value) {
    window.URL.revokeObjectURL(pdfPreviewBlobUrl.value)
    pdfPreviewBlobUrl.value = ''
  }
}

const loadProtectedPdfPreviewBlob = async (url) => {
  revokePdfBlobUrl()

  const token = localStorage.getItem('token')
  const headers = token ? { Authorization: `Bearer ${token}` } : {}
  const response = await fetch(url, {
    method: 'GET',
    cache: 'no-store',
    credentials: 'same-origin',
    headers,
  })

  if (!response.ok) {
    throw new Error(`PDF预览加载失败 (${response.status})`)
  }

  const blob = await response.blob()
  pdfPreviewBlobUrl.value = window.URL.createObjectURL(blob)
}

const syncPdfPreviewUrl = async () => {
  const sourceUrl = String(pdfPreviewUrl.value || '').trim()
  if (!sourceUrl) {
    revokePdfBlobUrl()
    return
  }

  const isProtectedPreview = isProtectedPdfPreviewUrl(sourceUrl)
  if (!isProtectedPreview) {
    revokePdfBlobUrl()
    return
  }

  try {
    await loadProtectedPdfPreviewBlob(sourceUrl)
  } catch (_error) {
    // Keep iframe empty on protected preview fetch failure to avoid showing raw JSON errors.
    revokePdfBlobUrl()
  }
}

const mdRelativeDir = computed(() => {
  const path = mdRelativePath.value
  if (!path) {
    return ''
  }
  const parts = path.split('/').filter(Boolean)
  parts.pop()
  return parts.join('/')
})

const normalizeRelativePath = (rawPath) => {
  const unified = String(rawPath || '').replace(/\\/g, '/')
  const segments = unified.split('/')
  const normalized = []
  for (const segment of segments) {
    if (!segment || segment === '.') {
      continue
    }
    if (segment === '..') {
      normalized.pop()
      continue
    }
    normalized.push(segment)
  }
  return normalized.join('/')
}

const buildApiHtmlAssetUrl = (relativeAssetPath) => {
  const assetPath = normalizeRelativePath(relativeAssetPath)
  if (!assetPath) {
    return ''
  }
  const encodedAsset = assetPath
    .split('/')
    .filter(Boolean)
    .map((item) => encodeURIComponent(item))
    .join('/')
  return `${apiPrefix}/html/${encodedAsset}`
}

const resolveAssetUrl = (rawUrl) => {
  const source = String(rawUrl || '').trim()
  if (!source) {
    return source
  }
  if (/^(https?:|data:|blob:|mailto:|tel:)/i.test(source)) {
    return source
  }
  if (source.startsWith('/')) {
    return source
  }

  const splitIndex = source.search(/[?#]/)
  const pathPart = splitIndex >= 0 ? source.slice(0, splitIndex) : source
  const suffix = splitIndex >= 0 ? source.slice(splitIndex) : ''

  const baseDir = mdRelativeDir.value
  const joined = baseDir ? `${baseDir}/${pathPart}` : pathPart
  const apiUrl = buildApiHtmlAssetUrl(joined)
  return apiUrl ? `${apiUrl}${suffix}` : source
}

const apiHtmlPrefixes = computed(() => {
  const prefixes = new Set([
    `${apiPrefix}/html/`,
    '/api/html/',
    '/docs/api/html/',
  ])
  return Array.from(prefixes)
})

const extractApiHtmlAsset = (rawUrl) => {
  const source = String(rawUrl || '').trim()
  if (!source) {
    return null
  }

  let parsed
  try {
    parsed = new URL(source, window.location.origin)
  } catch (_error) {
    return null
  }

  const pathname = parsed.pathname || ''
  const matchedPrefix = apiHtmlPrefixes.value.find((prefix) => pathname.startsWith(prefix))
  if (!matchedPrefix) {
    return null
  }

  const encodedPath = pathname.slice(matchedPrefix.length)
  const decodedPath = encodedPath
    .split('/')
    .filter(Boolean)
    .map((segment) => {
      try {
        return decodeURIComponent(segment)
      } catch (_error) {
        return segment
      }
    })
    .join('/')

  return {
    decodedPath,
    suffix: `${parsed.search || ''}${parsed.hash || ''}`,
  }
}

const toRelativeFromApiHtmlUrl = (rawUrl) => {
  const asset = extractApiHtmlAsset(rawUrl)
  if (!asset || !asset.decodedPath) {
    return rawUrl
  }

  const baseDir = mdRelativeDir.value
  if (!baseDir) {
    return rawUrl
  }

  if (asset.decodedPath === baseDir) {
    return `.${asset.suffix}`
  }

  if (asset.decodedPath.startsWith(`${baseDir}/`)) {
    return `${asset.decodedPath.slice(baseDir.length + 1)}${asset.suffix}`
  }

  return rawUrl
}

const rewriteMarkdownUrls = (markdownText, mapUrl) => {
  const text = String(markdownText || '')

  const rewriteInlineLink = text.replace(/\]\(([^)\n]+)\)/g, (full, inner) => {
    const raw = String(inner || '')
    const trimmed = raw.trim()
    if (!trimmed) {
      return full
    }

    let urlPart = trimmed
    let suffix = ''

    if (trimmed.startsWith('<')) {
      const end = trimmed.indexOf('>')
      if (end > 0) {
        urlPart = trimmed.slice(1, end)
        suffix = trimmed.slice(end + 1)
      }
    } else {
      const firstSpace = trimmed.search(/\s/)
      if (firstSpace > -1) {
        urlPart = trimmed.slice(0, firstSpace)
        suffix = trimmed.slice(firstSpace)
      }
    }

    const nextUrl = mapUrl(urlPart)
    if (!nextUrl || nextUrl === urlPart) {
      return full
    }

    const rebuilt = trimmed.startsWith('<') && urlPart !== trimmed
      ? `<${nextUrl}>${suffix}`
      : `${nextUrl}${suffix}`
    return `](${rebuilt})`
  })

  return rewriteInlineLink.replace(/\b(src|href)\s*=\s*"([^"]+)"/gi, (full, attr, url) => {
    const nextUrl = mapUrl(url)
    return nextUrl && nextUrl !== url ? `${attr}="${nextUrl}"` : full
  }).replace(/\b(src|href)\s*=\s*'([^']+)'/gi, (full, attr, url) => {
    const nextUrl = mapUrl(url)
    return nextUrl && nextUrl !== url ? `${attr}='${nextUrl}'` : full
  })
}

const normalizeTableCellText = (value) => String(value || '')
  .replace(/\r?\n+/g, '<br>')
  .replace(/\|/g, '\\|')
  .replace(/\s+/g, ' ')
  .trim()

const htmlTableToMarkdown = (tableHtml) => {
  if (typeof document === 'undefined') {
    return tableHtml
  }

  const wrap = document.createElement('div')
  wrap.innerHTML = tableHtml
  const table = wrap.querySelector('table')
  if (!table) {
    return tableHtml
  }

  const rows = Array.from(table.querySelectorAll('tr'))
    .map((tr) => Array.from(tr.children)
      .filter((cell) => cell.tagName === 'TH' || cell.tagName === 'TD')
      .map((cell) => ({
        isHeader: cell.tagName === 'TH',
        text: normalizeTableCellText(cell.textContent || ''),
      })))
    .filter((cells) => cells.length > 0)

  if (!rows.length) {
    return tableHtml
  }

  const headerRowIndex = rows.findIndex((cells) => cells.some((cell) => cell.isHeader))
  const useHeaderIndex = headerRowIndex >= 0 ? headerRowIndex : 0

  const headerCells = rows[useHeaderIndex].map((cell) => cell.text || ' ')
  const bodyRows = rows.filter((_row, index) => index !== useHeaderIndex)

  const maxColumns = Math.max(
    headerCells.length,
    ...bodyRows.map((row) => row.length),
    1,
  )

  const normalizeRowColumns = (cells) => {
    const next = Array.from({ length: maxColumns }, (_, index) => cells[index] || ' ')
    return `| ${next.join(' | ')} |`
  }

  const lines = []
  lines.push(normalizeRowColumns(headerCells))
  lines.push(`| ${Array.from({ length: maxColumns }, () => '---').join(' | ')} |`)
  bodyRows.forEach((row) => {
    lines.push(normalizeRowColumns(row.map((cell) => cell.text || ' ')))
  })

  return `\n${lines.join('\n')}\n`
}

const convertHtmlTablesToMarkdown = (markdownText) => {
  const text = String(markdownText || '')
  if (!text || !/<table[\s>]/i.test(text)) {
    return text
  }

  // Keep fenced code blocks untouched to avoid mutating literal examples.
  const segments = text.split(/(```[\s\S]*?```)/g)
  return segments.map((segment, index) => {
    if (index % 2 === 1) {
      return segment
    }
    return segment.replace(/<table[\s\S]*?<\/table>/gi, (tableHtml) => htmlTableToMarkdown(tableHtml))
  }).join('')
}

const toEditorMarkdown = (markdownText) => {
  const tableNormalized = convertHtmlTablesToMarkdown(markdownText)
  return rewriteMarkdownUrls(tableNormalized, (url) => resolveAssetUrl(url))
}

const fromEditorMarkdown = (markdownText) => rewriteMarkdownUrls(markdownText, (url) => toRelativeFromApiHtmlUrl(url))

const renderMarkdownToHtml = (markdownText) => {
  const rendered = md.render(markdownText || '')
  if (typeof document === 'undefined') {
    return rendered
  }

  const container = document.createElement('div')
  container.innerHTML = rendered
  container.querySelectorAll('img[src]').forEach((node) => {
    const nextSrc = resolveAssetUrl(node.getAttribute('src'))
    if (nextSrc) {
      node.setAttribute('src', nextSrc)
    }
  })
  return container.innerHTML
}

const uploadImageBlob = async (blob, fileName = 'pasted-image.png') => {
  if (!imageUploadApiUrl.value) {
    throw new Error('图片上传路径无效')
  }

  const fd = new FormData()
  fd.append('image', blob, fileName)

  const token = localStorage.getItem('token')
  const headers = token ? { Authorization: `Bearer ${token}` } : {}

  const resp = await fetch(imageUploadApiUrl.value, {
    method: 'POST',
    body: fd,
    credentials: 'same-origin',
    headers,
  })
  const data = await resp.json()
  if (!resp.ok || !data?.url) {
    throw new Error(data?.message || '图片上传失败')
  }
  return data
}

const syncDraftFromEditor = () => {
  if (!toastEditor.value) {
    return
  }
  const editorMarkdown = toastEditor.value.getMarkdown() || ''
  draftMarkdown.value = fromEditorMarkdown(editorMarkdown)
}

const syncEditorFromDraft = () => {
  if (!toastEditor.value) {
    return
  }
  const nextMarkdown = toEditorMarkdown(draftMarkdown.value || '')
  const current = toastEditor.value.getMarkdown() || ''
  if (current !== nextMarkdown) {
    toastEditor.value.setMarkdown(nextMarkdown)
  }
}

const focusToastEditor = () => {
  toastEditor.value?.focus()
}

const ensureToastEditor = async () => {
  await nextTick()
  if (toastEditor.value || !toastEditorHost.value) {
    return
  }

  toastEditor.value = new Editor({
    el: toastEditorHost.value,
    height: '100%',
    initialValue: toEditorMarkdown(draftMarkdown.value || ''),
    initialEditType: 'wysiwyg',
    previewStyle: 'vertical',
    usageStatistics: false,
    hooks: {
      addImageBlobHook: async (blob, callback) => {
        try {
          const data = await uploadImageBlob(blob, blob?.name || 'pasted-image.png')
          callback(data.url, blob?.name || 'image')
          nextTick(() => {
            syncDraftFromEditor()
          })
          statusText.value = '图片已插入'
        } catch (error) {
          const message = error?.message || '图片上传失败'
          statusText.value = message
          ElMessage.error(message)
        }
      },
    },
  })

  toastEditor.value.on('change', () => {
    syncDraftFromEditor()
  })
}

const appendUploadedImageMarkdown = async (blob, fileName) => {
  const data = await uploadImageBlob(blob, fileName)
  if (toastEditor.value) {
    toastEditor.value.insertText(`\n![](${data.url})\n`)
    syncDraftFromEditor()
  } else {
    draftMarkdown.value = `${draftMarkdown.value || ''}\n![](${data.url})\n`
  }
  statusText.value = '图片已插入'
}

const loadMarkdown = async () => {
  if (!markdownApiUrl.value) {
    statusText.value = '缺少预览路径参数 path'
    return
  }

  if (!markdownExists.value) {
    originalMarkdown.value = ''
    currentMarkdown.value = ''
    draftMarkdown.value = ''
    viewHtml.value = '<p>尚无OCR识别结果，请先点击 AI识别 生成 full.md。</p>'
    editing.value = false
    statusText.value = '未识别：请先执行 AI识别'
    return
  }

  loading.value = true
  statusText.value = '加载中...'
  try {
    const response = await fetch(markdownApiUrl.value, {
      method: 'GET',
      cache: 'no-store',
      credentials: 'same-origin',
    })

    if (!response.ok) {
      throw new Error(`加载失败 (${response.status})`)
    }

    const markdownText = await response.text()
    originalMarkdown.value = markdownText
    currentMarkdown.value = markdownText
    draftMarkdown.value = markdownText

    viewHtml.value = renderMarkdownToHtml(markdownText || '')
    editing.value = false
    statusText.value = '查看模式'
  } catch (error) {
    const message = error?.message || '加载失败'
    const isNotFound = /\(404\)/.test(message)
    if (isNotFound) {
      markdownExists.value = false
      originalMarkdown.value = ''
      currentMarkdown.value = ''
      draftMarkdown.value = ''
      viewHtml.value = '<p>尚无OCR识别结果，请先点击 AI识别 生成 full.md。</p>'
      statusText.value = '未识别：请先执行 AI识别'
    } else {
      statusText.value = message
      ElMessage.error(message)
    }
  } finally {
    loading.value = false
  }
}

const loadMarkdownMeta = async () => {
  pdfPreviewLoading.value = true

  if (!markdownMetaApiUrl.value) {
    revokePdfBlobUrl()
    pdfPreviewUrl.value = ''
    markdownExists.value = false
    pdfPreviewLoading.value = false
    return
  }

  try {
    const response = await fetch(markdownMetaApiUrl.value, {
      method: 'GET',
      cache: 'no-store',
      credentials: 'same-origin',
    })
    if (!response.ok) {
      revokePdfBlobUrl()
      pdfPreviewUrl.value = ''
      markdownExists.value = false
      return
    }

    const data = await response.json()
    markdownExists.value = typeof data?.markdown_exists === 'boolean' ? data.markdown_exists : true
    pdfPreviewUrl.value = normalizePreviewUrl(data?.pdf_preview_url || storagePdfPreviewApiUrl.value || '')
    await syncPdfPreviewUrl()
  } catch (_error) {
    revokePdfBlobUrl()
    pdfPreviewUrl.value = normalizePreviewUrl(storagePdfPreviewApiUrl.value || '')
    markdownExists.value = false
    await syncPdfPreviewUrl()
  } finally {
    pdfPreviewLoading.value = false
  }
}

const runAiRecognition = async () => {
  if (aiRecognizing.value) {
    return
  }

  const targetPdfPath = String(storagePdfPath.value || '').trim()
  if (!targetPdfPath) {
    ElMessage.warning('无法推导原始 PDF 路径，无法执行 AI识别')
    return
  }

  aiRecognizing.value = true
  statusText.value = 'AI识别中...'

  try {
    const token = localStorage.getItem('token')
    const headers = { 'Content-Type': 'application/json' }
    if (token) {
      headers.Authorization = `Bearer ${token}`
    }

    const response = await fetch(`${apiPrefix}/contracts/ai-parse`, {
      method: 'POST',
      headers,
      credentials: 'same-origin',
      body: JSON.stringify({ file_path: targetPdfPath }),
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(data?.message || 'AI识别失败')
    }

    await loadMarkdownMeta()
    await loadMarkdown()
    if (markdownExists.value) {
      statusText.value = 'AI识别成功，可进入编辑'
      ElMessage.success('AI识别完成，已生成可编辑内容')
    } else {
      statusText.value = 'AI识别已完成，但尚未发现 full.md'
      ElMessage.warning('AI识别已完成，但未找到 full.md')
    }
  } catch (error) {
    const message = error?.message || 'AI识别失败'
    statusText.value = message
    ElMessage.error(message)
  } finally {
    aiRecognizing.value = false
  }
}

const switchToEdit = async () => {
  if (!markdownExists.value) {
    ElMessage.warning('暂无 OCR full.md，请先执行 AI识别')
    return
  }

  editing.value = true
  draftMarkdown.value = currentMarkdown.value || ''
  statusText.value = '编辑模式：所见即所得'

  await ensureToastEditor()
  syncEditorFromDraft()
  toastEditor.value?.changeMode('wysiwyg', false)
  focusToastEditor()
}

const toggleEditMode = async () => {
  if (editing.value) {
    switchToView()
    return
  }
  await switchToEdit()
}

const switchToView = () => {
  syncDraftFromEditor()
  currentMarkdown.value = draftMarkdown.value || ''
  viewHtml.value = renderMarkdownToHtml(currentMarkdown.value || '')
  editing.value = false
  statusText.value = '查看模式'
}

const cancelEdit = () => {
  draftMarkdown.value = originalMarkdown.value || ''
  viewHtml.value = renderMarkdownToHtml(originalMarkdown.value || '')
  currentMarkdown.value = originalMarkdown.value
  switchToView()
}

const saveMarkdown = async () => {
  if (!editing.value || !markdownApiUrl.value) {
    return
  }

  saving.value = true
  statusText.value = '保存中...'

  try {
    const editorMarkdown = toastEditor.value ? (toastEditor.value.getMarkdown() || '') : (draftMarkdown.value || '')
    const nextMarkdown = fromEditorMarkdown(editorMarkdown)
    const token = localStorage.getItem('token')
    const headers = { 'Content-Type': 'application/json' }
    if (token) {
      headers.Authorization = `Bearer ${token}`
    }

    const response = await fetch(markdownApiUrl.value, {
      method: 'PUT',
      headers,
      body: JSON.stringify({ markdown: nextMarkdown }),
      credentials: 'same-origin',
    })
    const data = await response.json()

    if (!response.ok) {
      throw new Error(data?.message || '保存失败')
    }

    originalMarkdown.value = nextMarkdown
    currentMarkdown.value = nextMarkdown
    switchToView()
    statusText.value = '保存成功'
    ElMessage.success('保存成功')
  } catch (error) {
    const message = error?.message || '保存失败'
    statusText.value = message
    ElMessage.error(message)
  } finally {
    saving.value = false
  }
}

watch(
  () => mdRelativePath.value,
  async () => {
    await loadMarkdownMeta()
    await loadMarkdown()
  },
)

onMounted(async () => {
  await loadMarkdownMeta()
  await loadMarkdown()
})

onBeforeUnmount(() => {
  revokePdfBlobUrl()
  if (toastEditor.value) {
    toastEditor.value.destroy()
    toastEditor.value = null
  }
})

</script>

<style scoped>
.preview-page {
  width: 100%;
  height: 100vh;
  display: grid;
  grid-template-columns: 4fr 6fr;
  gap: 12px;
  padding: 12px;
  box-sizing: border-box;
  background: #f6f8fa;
}

.left-pane,
.right-pane {
  min-width: 0;
  min-height: 0;
  border: 1px solid #d0d7de;
  border-radius: 10px;
  background: #ffffff;
  overflow: hidden;
}

.left-pane,
.right-pane {
  display: flex;
  flex-direction: column;
}

.pane-title,
.toolbar {
  padding: 10px 12px;
  border-bottom: 1px solid #e5e7eb;
  background: #f8fafc;
}

.pane-title {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.toolbar-left {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.toolbar-group-buttons {
  border: 1px solid #d2d2d7;
  border-radius: 10px;
  overflow: hidden;
  background: #ffffff;
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.03);
}

.standalone-btn {
  height: 34px;
  padding: 0 12px;
  border: 1px solid #d2d2d7;
  border-radius: 10px;
  background: #ffffff;
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 500;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.standalone-btn:hover:not(:disabled) {
  background: #f5f5f7;
}

.standalone-btn:disabled {
  color: #b6b6bd;
  cursor: not-allowed;
  background: #fafafa;
}

.group-btn {
  height: 34px;
  padding: 0 12px;
  border: none;
  border-left: 1px solid #e5e5ea;
  background: #ffffff;
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 500;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.group-btn:first-child {
  border-left: none;
}

.group-btn:hover:not(:disabled) {
  background: #f5f5f7;
}

.group-btn:disabled {
  color: #b6b6bd;
  cursor: not-allowed;
  background: #fafafa;
}

.btn-icon {
  width: 14px;
  height: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.btn-icon svg {
  width: 14px;
  height: 14px;
}

.state-btn.is-viewing {
  color: #1f2937;
}

.ai-btn {
  color: #0f766e;
}

.ai-btn:hover:not(:disabled) {
  background: #ecfeff;
  color: #0f766e;
}

.btn-spinner {
  width: 14px;
  height: 14px;
  border-radius: 999px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  animation: btn-spin 0.8s linear infinite;
}

@keyframes btn-spin {
  to {
    transform: rotate(360deg);
  }
}

.state-btn.is-editing {
  background: #eef5ff;
  color: #1d4ed8;
}

.state-btn.is-editing:hover {
  background: #e3efff;
}

.toolbar-status {
  color: #6b7280;
  font-size: 12px;
  white-space: nowrap;
}

.editor-host {
  flex: 1;
  min-height: 0;
  padding: 12px;
  box-sizing: border-box;
}

.toast-editor-host {
  width: 100%;
  height: 100%;
  min-height: 0;
}

.toast-editor-host :deep(.toastui-editor-defaultUI) {
  height: 100%;
  display: flex;
  flex-direction: column;
  border: 1px solid #d0d7de;
  border-radius: 8px;
  overflow: hidden;
}

.toast-editor-host :deep(.toastui-editor-toolbar) {
  flex: 0 0 auto;
  border-bottom: 1px solid #e5e7eb;
}

.toast-editor-host :deep(.toastui-editor-main) {
  flex: 1 1 auto;
  min-height: 0;
}

.toast-editor-host :deep(.toastui-editor-main-container) {
  height: 100%;
}

.toast-editor-host :deep(.toastui-editor-ww-container) {
  height: 100%;
}

.toast-editor-host :deep(.toastui-editor.ww-mode) {
  height: 100%;
  overflow: auto;
}

.toast-editor-host :deep(.toastui-editor.ww-mode .ProseMirror.toastui-editor-contents) {
  min-height: 100%;
  box-sizing: border-box;
}

.toast-editor-host :deep(.toastui-editor-contents) {
  font-size: 13px;
  line-height: 1.6;
}

.markdown-view-wrap {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.markdown-scroll {
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  padding: 18px;
}

.markdown-body {
  line-height: 1.6;
  word-break: break-word;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) {
  margin-top: 24px;
  margin-bottom: 16px;
  line-height: 1.25;
  font-weight: 600;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2) {
  border-bottom: 1px solid #d8dee4;
  padding-bottom: 0.3em;
}

.markdown-body :deep(p),
.markdown-body :deep(ul),
.markdown-body :deep(ol),
.markdown-body :deep(blockquote),
.markdown-body :deep(table),
.markdown-body :deep(pre) {
  margin-top: 0;
  margin-bottom: 16px;
}

.markdown-body :deep(pre) {
  background: #f6f8fa;
  border-radius: 8px;
  padding: 16px;
  overflow: auto;
}

.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
}

.markdown-body :deep(code) {
  font-size: 85%;
  background: rgba(175, 184, 193, 0.2);
  border-radius: 6px;
  padding: 0.2em 0.4em;
}

.markdown-body :deep(table) {
  border-collapse: collapse;
  max-width: 100%;
}

.markdown-body :deep(a) {
  color: #0969da;
  text-decoration: none;
}

.markdown-body :deep(a:hover) {
  text-decoration: underline;
}

.markdown-body :deep(blockquote) {
  margin-left: 0;
  padding: 0 1em;
  color: #57606a;
  border-left: 0.25em solid #d0d7de;
}

.markdown-body :deep(hr) {
  border: 0;
  height: 0.25em;
  padding: 0;
  margin: 24px 0;
  background: #d0d7de;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #d0d7de;
  padding: 6px 13px;
}

.pdf-frame {
  width: 100%;
  height: 100%;
  border: none;
  flex: 1;
}

.pdf-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  font-size: 13px;
  padding: 12px;
  box-sizing: border-box;
}

@media (max-width: 1100px) {
  .preview-page {
    grid-template-columns: 1fr;
    grid-template-rows: 48vh auto;
  }

  .toolbar {
    flex-wrap: wrap;
  }
}
</style>
