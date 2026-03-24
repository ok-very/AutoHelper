import { Mark, mergeAttributes } from '@tiptap/core'

export interface FontSizeOptions {
  allowedSizes: string[]
}

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    fontSize: {
      setFontSize: (size: string) => ReturnType
      unsetFontSize: () => ReturnType
    }
  }
}

export const FontSize = Mark.create<FontSizeOptions>({
  name: 'fontSize',

  addOptions() {
    return {
      allowedSizes: ['8pt', '11pt'],
    }
  },

  addAttributes() {
    return {
      size: {
        default: null,
        parseHTML: (element) => {
          const size = element.style.fontSize
          if (size && this.options.allowedSizes.includes(size)) {
            return size
          }
          return null
        },
        renderHTML: (attributes) => {
          if (!attributes.size) return {}
          return { style: `font-size: ${attributes.size}` }
        },
      },
    }
  },

  parseHTML() {
    return [
      {
        tag: 'span',
        getAttrs: (element) => {
          const el = element as HTMLElement
          const size = el.style.fontSize
          if (size && this.options.allowedSizes.includes(size)) {
            return { size }
          }
          return false
        },
      },
    ]
  },

  renderHTML({ HTMLAttributes }) {
    return ['span', mergeAttributes(HTMLAttributes), 0]
  },

  addCommands() {
    return {
      setFontSize:
        (size: string) =>
        ({ commands }) => {
          if (!this.options.allowedSizes.includes(size)) return false
          return commands.setMark(this.name, { size })
        },
      unsetFontSize:
        () =>
        ({ commands }) => {
          return commands.unsetMark(this.name)
        },
    }
  },
})
