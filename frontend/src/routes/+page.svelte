<script lang="ts">
  import Icon from '#lib/components/Icon.svelte';
  import ListingArtwork from '#lib/components/ListingArtwork.svelte';
  import ListingCard from '#lib/components/ListingCard.svelte';
  import PreviewNotice from '#lib/components/PreviewNotice.svelte';
  import { categories, demoListings } from '#lib/demo/marketplace.ts';
</script>

<svelte:head
  ><title>Adify — Good brands meet the right people</title><meta
    name="description"
    content="Discover a new place for internet advertising partnerships. Explore website, social media, video, stream, and in-app advertising on Adify."
  /></svelte:head
>

<section class="hero container" aria-labelledby="hero-heading">
  <div class="hero-copy">
    <span class="eyebrow"><span class="status-dot"></span> A SPACE FOR BETTER CONNECTIONS</span>
    <h1 id="hero-heading">Good brands.<br />The right people.<br /><span>A little Adify.</span></h1>
    <p>
      Find a place for your next big idea. Connect with advertising providers and bring your brand
      to the right audience.
    </p>
    <div class="hero-actions">
      <a href="/listings" class="button button-dark"
        >Explore the marketplace <Icon name="arrow" size={18} /></a
      ><a href="/how-it-works" class="text-link">How it works <Icon name="chevron" size={15} /></a>
    </div>
    <div class="hero-footnote">
      <span class="mini-avatars" aria-hidden="true"><i>c</i><i>p</i></span><span
        >For customers with ideas.<br /><strong>For providers with possibilities.</strong></span
      >
    </div>
  </div>
  <div class="hero-visual" aria-hidden="true">
    <span class="hero-orbit"></span><span class="hero-visual-label"
      >YOUR NEXT CONNECTION STARTS HERE</span
    >
    <div class="hero-mini-card hero-browser"><ListingArtwork category="website-banners" /></div>
    <div class="hero-main-card">
      <ListingArtwork category="social-media-posts" />
      <div class="hero-card-caption">
        <span><b>A story worth sharing.</b><small>Social media · Made for your brand</small></span
        ><span class="hero-caption-arrow">↗</span>
      </div>
    </div>
    <div class="connection-note">
      <span>✳</span>
      <div>The right fit.<br /><strong>A new possibility.</strong></div>
    </div>
    <span class="hero-spark">✳</span><span class="hero-scroll-note">a good place to grow ↗</span>
  </div>
</section>

<section class="category-section" aria-labelledby="categories-heading">
  <div class="container">
    <div class="section-heading compact">
      <h2 id="categories-heading">Different spaces. <span>Endless possibilities.</span></h2>
      <span class="section-aside">Internet advertising, all in one place</span>
    </div>
    <ul class="category-grid">
      {#each categories as category (category.id)}<li>
          <a href={`/listings#${category.id}`}
            ><span class="category-icon"><Icon name={category.icon} size={24} /></span><span
              >{category.short}</span
            ><Icon name="arrow" size={15} /></a
          >
        </li>{/each}
    </ul>
  </div>
</section>

<section class="container section-space" aria-labelledby="listings-heading">
  <div class="section-heading">
    <div>
      <span class="eyebrow">THE MARKETPLACE</span>
      <h2 id="listings-heading">Your next partnership<br />could start here.</h2>
    </div>
    <a href="/listings" class="text-link">Explore all listings <Icon name="arrow" size={18} /></a>
  </div>
  <PreviewNotice />
  <div class="listing-grid">
    {#each demoListings.slice(0, 3) as listing (listing.slug)}<ListingCard {listing} />{/each}
  </div>
</section>

<section class="container connection-section" aria-labelledby="connection-heading">
  <div class="connection-intro">
    <span class="eyebrow">A LITTLE LESS BACK AND FORTH</span>
    <h2 id="connection-heading">Great partnerships<br />start with a good fit.</h2>
    <p>
      From the first hello to the final placement, Adify is being built to keep your advertising
      work in one place.
    </p>
    <a href="/how-it-works" class="text-link">Get to know Adify <Icon name="arrow" size={18} /></a>
  </div>
  <ol class="connection-steps">
    <li>
      <span>01</span>
      <div>
        <h3>Find your people</h3>
        <p>Explore internet advertising offers and requests across six categories.</p>
      </div>
      <Icon name="search" size={22} />
    </li>
    <li>
      <span>02</span>
      <div>
        <h3>Get on the same page</h3>
        <p>Discuss the idea, placement requirements, and scope before work starts.</p>
      </div>
      <Icon name="social" size={22} />
    </li>
    <li>
      <span>03</span>
      <div>
        <h3>Make something happen</h3>
        <p>Agree on an order, share materials, and review the finished work.</p>
      </div>
      <Icon name="check" size={22} />
    </li>
  </ol>
</section>

<section class="container final-section">
  <div class="final-banner">
    <span class="banner-spark" aria-hidden="true">✳</span>
    <div>
      <span class="eyebrow">BIG IDEAS DESERVE THE RIGHT SPACE</span>
      <h2>Find yours on Adify.</h2>
    </div>
    <a href="/listings" class="button button-light"
      >Take a look around <Icon name="arrow" size={18} /></a
    >
  </div>
</section>
