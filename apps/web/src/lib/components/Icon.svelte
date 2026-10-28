<script lang="ts">
  export type IconName =
    | 'arrow'
    | 'search'
    | 'menu'
    | 'close'
    | 'globe'
    | 'article'
    | 'social'
    | 'video'
    | 'stream'
    | 'mobile'
    | 'check'
    | 'shield'
    | 'chevron'
    | 'clock';
  let { name, size = 20 }: { name: IconName; size?: number } = $props();
  const paths: Record<IconName, string> = {
    arrow: 'M5 12h14M13 6l6 6-6 6',
    search: 'm20 20-5-5M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0',
    menu: 'M4 6h16M4 12h16M4 18h16',
    close: 'm6 6 12 12M6 18 18 6',
    globe: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0M3 12h18M12 3c5 5 5 13 0 18-5-5-5-13 0-18',
    article: 'M5 3h14v18H5zM8 7h8M8 11h8M8 15h5',
    social: 'M21 11a9 9 0 0 1-9 9H4l1-5a9 9 0 1 1 16-4M8 10h8M8 14h5',
    video: 'm10 8 6 4-6 4zM3 5h18v14H3z',
    stream:
      'M8 8a6 6 0 0 0 0 8M16 8a6 6 0 0 1 0 8M5 5a10 10 0 0 0 0 14M19 5a10 10 0 0 1 0 14M12 11v2',
    mobile: 'M7 2h10v20H7zM10 18h4',
    check: 'm5 12 4 4L19 6',
    shield: 'm12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6zM8 12l3 3 5-6',
    chevron: 'm9 5 7 7-7 7',
    clock: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0M12 7v5l3 2',
  };
</script>

<svg
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="1.6"
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"><path d={paths[name]} /></svg
>
