<script lang="ts">
  let { category, large = false }: { category: string; large?: boolean } = $props();
</script>

<div
  class="listing-art"
  class:large
  class:social-art={category === 'social-media-posts'}
  class:banner-art={category === 'website-banners'}
  class:video-art={category === 'video-integrations'}
  class:article-art={category === 'sponsored-articles'}
  class:stream-art={category === 'stream-ads'}
  class:app-art={category === 'in-app-mobile-ads'}
  aria-hidden="true"
>
  {#if category === 'social-media-posts'}
    <div class="art-caption">a little<br /><em>everyday.</em></div>
    <div class="still-life">
      <div class="vase"><i></i></div>
      <div class="stem stem-one"></div>
      <div class="stem stem-two"></div>
      <div class="leaf leaf-one"></div>
      <div class="leaf leaf-two"></div>
      <div class="leaf leaf-three"></div>
      <div class="still-life-shadow"></div>
    </div>
    <span class="art-corner">STORIES THAT STAY</span>
  {:else if category === 'website-banners'}
    <div class="browser-art">
      <div class="browser-bar"><i></i><i></i><i></i><span>the digital daily</span></div>
      <div class="browser-body">
        <span class="tiny-label">DESIGN / CULTURE / IDEAS</span><strong
          >Good design.<br />Great company.</strong
        >
        <div class="mock-banner">
          <span>YOUR BRAND,<br /><b>right here.</b></span><span class="mock-banner-arrow">↗</span>
        </div>
        <div class="mock-lines"><i></i><i></i><i></i></div>
      </div>
    </div>
  {:else if category === 'video-integrations'}
    <span class="video-kicker">A FRESH PERSPECTIVE</span><span class="video-type"
      >Made to<br /><em>be seen.</em></span
    >
    <div class="video-orbit orbit-one"></div>
    <div class="video-orbit orbit-two"></div>
    <span class="play-disc">▶</span><span class="video-duration">01:24</span>
  {:else if category === 'sponsored-articles'}
    <div class="article-sheet">
      <span>THE SLOW EDIT</span>
      <div class="article-rule"></div>
      <strong>Small changes.<br /><em>Better living.</em></strong>
      <div class="article-image"><div></div></div>
      <div class="mock-lines"><i></i><i></i></div>
    </div>
    <span class="article-stamp">a story<br />worth sharing</span>
  {:else if category === 'stream-ads'}
    <span class="live-tag"><i></i> LIVE</span>
    <div class="stream-rings"></div>
    <span class="stream-type">In good<br /><em>company.</em></span>
    <div class="stream-wave"><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div>
  {:else}
    <span class="app-type">Small screen.<br /><em>Big possibility.</em></span>
    <div class="phone-art">
      <div class="phone-island"></div>
      <div class="phone-sun"></div>
      <div class="phone-hill"></div>
      <div class="phone-ad">Your next<br /><b>good find.</b><span>DISCOVER →</span></div>
    </div>
  {/if}
</div>
