"""Seed the catalogue with a bilingual demo assortment.

Idempotent: re-running updates rather than duplicating, so it is safe to point
at a long-lived staging database.

Product photography is pulled from LoremFlickr, which proxies Creative Commons
Flickr images by keyword. That keeps the repository free of binary assets while
still showing real photographs rather than grey placeholder boxes. Swapping in
a real DAM means changing ``image_url`` below and nothing else.
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

from sqlalchemy import select

from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.db.session import get_session_factory
from app.modules.catalog.models import Brand, Category, Product, ProductImage, ProductVariant
from app.modules.identity.models import Address, User
from app.modules.inventory.models import StockItem
from app.shared.slugify import slugify

logger = get_logger(__name__)


def image_url(keywords: str, lock: int, width: int = 1000, height: int = 1250) -> str:
    return f"https://loremflickr.com/{width}/{height}/{keywords}?lock={lock}"


CATEGORIES = [
    ("hem", {"sv": "Hem", "en": "Home"}, "hem", 0),
    ("mobler", {"sv": "Möbler", "en": "Furniture"}, "hem.mobler", 1),
    ("sittmobler", {"sv": "Sittmöbler", "en": "Seating"}, "hem.mobler.sittmobler", 2),
    ("bord", {"sv": "Bord", "en": "Tables"}, "hem.mobler.bord", 2),
    ("belysning", {"sv": "Belysning", "en": "Lighting"}, "hem.belysning", 1),
    ("textil", {"sv": "Textil", "en": "Textiles"}, "hem.textil", 1),
    ("kok", {"sv": "Kök", "en": "Kitchen"}, "hem.kok", 1),
    ("elektronik", {"sv": "Elektronik", "en": "Electronics"}, "elektronik", 0),
    ("ljud", {"sv": "Ljud", "en": "Audio"}, "elektronik.ljud", 1),
    ("arbetsplats", {"sv": "Arbetsplats", "en": "Workspace"}, "elektronik.arbetsplats", 1),
    ("utomhus", {"sv": "Utomhus", "en": "Outdoor"}, "utomhus", 0),
    ("friluft", {"sv": "Friluftsliv", "en": "Outdoor life"}, "utomhus.friluft", 1),
]

BRANDS = [
    ("Vasterbo", "SE"),
    ("Nordljus", "SE"),
    ("Skogsro", "SE"),
    ("Hallby Audio", "SE"),
    ("Kallvik", "FI"),
    ("Ostersund Works", "SE"),
]

# (slug, category_path, brand, title_sv, title_en, desc_sv, desc_en,
#  price_kr, compare_kr, keywords, tags, options)
PRODUCTS = [
    ("fatolj-hedvig", "hem.mobler.sittmobler", "Vasterbo",
     "Fåtölj Hedvig", "Hedvig Armchair",
     "Formpressad ek och ullklädsel från Gotland. Ramen är limträ, inte spånskiva, "
     "och stolen går att klä om i stället för att slängas.",
     "Moulded oak with Gotland wool upholstery. The frame is glulam rather than "
     "particle board, so the chair can be reupholstered instead of replaced.",
     6490, 7990, "armchair,wool", ["ek", "ull"],
     [{"colour": "havre"}, {"colour": "kolgra"}]),
    ("soffa-mariefred", "hem.mobler.sittmobler", "Vasterbo",
     "Soffa Mariefred 3-sits", "Mariefred 3-seat Sofa",
     "Tre sitsar, avtagbara klädslar och fjäderpackade dynor som återfår formen "
     "efter en kväll i soffan.",
     "Three seats, removable covers, and spring-packed cushions that recover "
     "their shape after an evening on them.",
     14900, None, "sofa,livingroom", ["ull", "avtagbar"],
     [{"colour": "sand"}, {"colour": "mossgron"}]),
    ("pall-lodose", "hem.mobler.sittmobler", "Skogsro",
     "Pall Lödöse", "Lödöse Stool",
     "Massiv björk, staplingsbar tre i höjd. Sitsen är oljad, inte lackad, så "
     "repor går att slipa bort.",
     "Solid birch, stacks three high. The seat is oiled rather than lacquered, so "
     "scratches sand out.",
     1290, None, "stool,wood", ["bjork"], [{"height": "45"}, {"height": "65"}]),
    ("matbord-ransater", "hem.mobler.bord", "Skogsro",
     "Matbord Ransäter", "Ransäter Dining Table",
     "180 cm massiv ask med iläggsskiva. Bordsskivan är 30 mm tjock och sitter på "
     "insexskruvar, inte lim.",
     "180 cm solid ash with an extension leaf. The top is 30 mm thick and bolted "
     "rather than glued.",
     11900, 13500, "diningtable,wood", ["ask", "utdragbar"],
     [{"size": "180"}, {"size": "220"}]),
    ("sidobord-visby", "hem.mobler.bord", "Kallvik",
     "Sidobord Visby", "Visby Side Table",
     "Pulverlackerat stål med kalkstensskiva. Väger 9 kg, står stilla på trägolv.",
     "Powder-coated steel with a limestone top. Nine kilos, and it stays put on a "
     "wooden floor.",
     2490, None, "sidetable,stone", ["sten", "stal"], [{"colour": "svart"}]),
    ("golvlampa-aurora", "hem.belysning", "Nordljus",
     "Golvlampa Aurora", "Aurora Floor Lamp",
     "Opalglas och mässing, dimbar till 5 %. Lampan tar E27, så glödlampan är inte "
     "inbyggd och kan bytas.",
     "Opal glass and brass, dimmable to 5%. Takes a standard E27, so the bulb is "
     "replaceable rather than sealed in.",
     3290, None, "floorlamp,lighting", ["massing", "dimbar"],
     [{"finish": "massing"}, {"finish": "svart"}]),
    ("bordslampa-lykta", "hem.belysning", "Nordljus",
     "Bordslampa Lykta", "Lykta Table Lamp",
     "Handblåst glas i Småland. Varje kupa har små variationer, det är inte ett fel.",
     "Hand-blown in Småland. Each shade varies slightly; that is the process, not "
     "a defect.",
     1690, 1990, "tablelamp,glass", ["glas"], [{"colour": "rok"}, {"colour": "klar"}]),
    ("pendel-hamn", "hem.belysning", "Nordljus",
     "Pendel Hamn", "Hamn Pendant",
     "Emaljerad plåt, 40 cm diameter. Sladden är textilklädd och 3 meter lång.",
     "Enamelled steel, 40 cm across. Three metres of fabric-covered cord.",
     2190, None, "pendantlight,lamp", ["emalj"], [{"colour": "gron"}, {"colour": "cream"}]),
    ("ullpladd-lappland", "hem.textil", "Skogsro",
     "Ullpläd Lappland", "Lappland Wool Throw",
     "130x180 cm lammull, vävd i Sverige. Tvättas i ullprogram, tål 30 grader.",
     "130x180 cm lambswool, woven in Sweden. Machine washable on a wool cycle at 30.",
     1490, None, "woolblanket,textile", ["ull", "vavd"],
     [{"colour": "gra"}, {"colour": "rodbrun"}]),
    ("matta-kust", "hem.textil", "Kallvik",
     "Matta Kust", "Kust Rug",
     "Handvävd jute, 200x300 cm. Fäller lite första månaden och slutar sedan.",
     "Hand-woven jute, 200x300 cm. Sheds a little for the first month, then stops.",
     4290, 4990, "jauterug,rug", ["jute"], [{"size": "200x300"}, {"size": "160x230"}]),
    ("kuddfodral-skarhamn", "hem.textil", "Vasterbo",
     "Kuddfodral Skärhamn", "Skärhamn Cushion Cover",
     "50x50 cm tvättat lin med dold dragkedja.",
     "50x50 cm washed linen with a hidden zip.",
     349, None, "cushion,linen", ["lin"], [{"colour": "blek"}, {"colour": "indigo"}]),
    ("gjutjarnspanna-smedja", "hem.kok", "Ostersund Works",
     "Gjutjärnspanna Smedja", "Smedja Cast Iron Pan",
     "28 cm, förbränd med linolja. Tål ugn till 250 grader och håller längre än ägaren.",
     "28 cm, pre-seasoned with linseed oil. Oven-safe to 250C and will outlast its owner.",
     1190, None, "castironpan,cooking", ["gjutjarn"], [{"size": "28"}, {"size": "24"}]),
    ("knivset-sagverk", "hem.kok", "Ostersund Works",
     "Knivset Sågverk", "Sågverk Knife Set",
     "Tre knivar i pulvermetallstål, 61 HRC. Slipas om av tillverkaren i tio år.",
     "Three powder-steel knives at 61 HRC. The maker resharpens them for ten years.",
     3490, 3990, "kitchenknife,knives", ["stal"], [{"pieces": "3"}]),
    ("kaffebryggare-morgon", "hem.kok", "Kallvik",
     "Kaffebryggare Morgon", "Morgon Coffee Brewer",
     "Bryggtemperatur 94 grader, glaskanna. Ingen app, ingen wifi, en knapp.",
     "Brews at 94C into a glass carafe. No app, no wifi, one button.",
     2790, None, "coffeemaker,kitchen", ["glas"], [{"colour": "stal"}]),
    ("hogtalare-kajen", "elektronik.ljud", "Hallby Audio",
     "Högtalare Kajen", "Kajen Speaker",
     "Aktiv tvåvägshögtalare med ekfaner. Har fysisk volymratt och linjeingång.",
     "Active two-way speaker in oak veneer. Physical volume dial and a line input.",
     8990, 9990, "speaker,audio", ["ek", "bluetooth"],
     [{"colour": "ek"}, {"colour": "valnot"}]),
    ("horlurar-tystnad", "elektronik.ljud", "Hallby Audio",
     "Hörlurar Tystnad", "Tystnad Headphones",
     "Över örat, 40 timmar batteri, utbytbara öronkuddar och batteri.",
     "Over-ear, 40 hours of battery, with replaceable pads and cell.",
     4490, None, "headphones,audio", ["anc"], [{"colour": "svart"}, {"colour": "sand"}]),
    ("skivspelare-spar", "elektronik.ljud", "Hallby Audio",
     "Skivspelare Spår", "Spår Turntable",
     "Remdriven, förmonterad pickup, inbyggt RIAA-steg som går att koppla förbi.",
     "Belt-driven with a pre-mounted cartridge and a built-in RIAA stage you can bypass.",
     6990, None, "turntable,vinyl", ["vinyl"], [{"colour": "svart"}]),
    ("skrivbord-station", "elektronik.arbetsplats", "Ostersund Works",
     "Skrivbord Station", "Station Standing Desk",
     "Elektriskt höj- och sänkbart, 62-128 cm, 100 kg lyftkapacitet, linoleumskiva.",
     "Electric sit-stand, 62-128 cm, rated to 100 kg, linoleum top.",
     9490, 10900, "standingdesk,office", ["hojbart"],
     [{"size": "140x70"}, {"size": "160x80"}]),
    ("skrivbordslampa-fokus", "elektronik.arbetsplats", "Nordljus",
     "Skrivbordslampa Fokus", "Fokus Desk Lamp",
     "CRI 95, färgtemperatur 2700-5000 K, bordsklämma ingår.",
     "CRI 95, 2700-5000 K colour temperature, desk clamp included.",
     1890, None, "desklamp,office", ["led"], [{"colour": "vit"}, {"colour": "grafit"}]),
    ("tangentbord-tryck", "elektronik.arbetsplats", "Kallvik",
     "Tangentbord Tryck", "Tryck Keyboard",
     "Svensk layout, hot-swap-socklar och QMK. Aluminiumchassi, 1,1 kg.",
     "Swedish layout, hot-swap sockets and QMK. Aluminium case, 1.1 kg.",
     2490, None, "keyboard,desk", ["mekaniskt"],
     [{"switch": "brun"}, {"switch": "rod"}]),
    ("ryggsack-fjall", "utomhus.friluft", "Skogsro",
     "Ryggsäck Fjäll 30L", "Fjäll 30L Backpack",
     "Återvunnen ripstop, rullstängning, 30 liter. Sömmarna är tejpade, inte bara sydda.",
     "Recycled ripstop, roll-top closure, 30 litres. Seams are taped, not just stitched.",
     2190, 2590, "backpack,hiking", ["atervunnet"],
     [{"colour": "mossa"}, {"colour": "kol"}]),
    ("termos-vinter", "utomhus.friluft", "Ostersund Works",
     "Termos Vinter 0,9L", "Vinter 0.9L Flask",
     "Rostfritt dubbelväggigt stål, håller 70 grader i tolv timmar.",
     "Double-walled stainless steel, holds 70C for twelve hours.",
     599, None, "thermos,outdoor", ["stal"], [{"size": "0.9"}, {"size": "0.5"}]),
    ("regnjacka-kust", "utomhus.friluft", "Skogsro",
     "Regnjacka Kust", "Kust Rain Jacket",
     "PFAS-fri impregnering, 20 000 mm vattenpelare, tejpade sömmar.",
     "PFAS-free durable water repellent, 20,000 mm hydrostatic head, taped seams.",
     3490, None, "rainjacket,outdoor", ["pfas-fri"],
     [{"size": "M"}, {"size": "L"}, {"size": "XL"}]),
    ("stormkok-lager", "utomhus.friluft", "Ostersund Works",
     "Stormkök Läger", "Läger Camp Stove",
     "Kokar en liter på tre minuter i blåst. Går på gas eller rödsprit.",
     "Boils a litre in three minutes in wind. Runs on gas or denatured alcohol.",
     1290, 1490, "campstove,camping", ["friluft"], [{"fuel": "gas"}]),
]


async def seed() -> None:
    configure_logging(debug=True)
    factory = get_session_factory()

    async with factory() as session:
        categories: dict[str, Category] = {}
        for slug, name, path, depth in CATEGORIES:
            existing = await session.scalar(select(Category).where(Category.path == path))
            if existing is None:
                existing = Category(slug=slug, name=name, path=path, depth=depth)
                session.add(existing)
            else:
                existing.name = name
            categories[path] = existing
        await session.flush()

        for path, category in categories.items():
            if "." in path:
                category.parent_id = categories[path.rsplit(".", 1)[0]].id

        brands: dict[str, Brand] = {}
        for name, country in BRANDS:
            slug = slugify(name)
            existing = await session.scalar(select(Brand).where(Brand.slug == slug))
            if existing is None:
                existing = Brand(slug=slug, name=name, country_code=country)
                session.add(existing)
            brands[name] = existing
        await session.flush()

        for index, row in enumerate(PRODUCTS):
            (
                slug, cat_path, brand_name, title_sv, title_en,
                desc_sv, desc_en, price_kr, compare_kr, keywords, tags, option_sets,
            ) = row

            product = await session.scalar(select(Product).where(Product.slug == slug))
            if product is None:
                product = Product(slug=slug)
                session.add(product)

            product.title = {"sv": title_sv, "en": title_en}
            product.description = {"sv": desc_sv, "en": desc_en}
            product.highlights = {
                "sv": ["Fri frakt över 995 kr", "60 dagars öppet köp", "Skickas från Sverige"],
                "en": ["Free shipping over 995 kr", "60-day returns", "Ships from Sweden"],
            }
            product.category_id = categories[cat_path].id
            product.brand_id = brands[brand_name].id
            product.is_published = True
            product.tags = tags
            product.rating_average = Decimal(str(round(3.9 + (index % 11) * 0.1, 1)))
            product.rating_count = 12 + index * 7
            await session.flush()

            if not product.images:
                for position in range(3):
                    session.add(
                        ProductImage(
                            product_id=product.id,
                            url=image_url(keywords, lock=1000 + index * 10 + position),
                            alt_text={"sv": title_sv, "en": title_en},
                            position=position,
                            width=1000,
                            height=1250,
                        )
                    )

            for variant_index, options in enumerate(option_sets):
                sku = f"NM-{slug[:12].upper().replace('-', '')}-{variant_index + 1:02d}"
                variant = await session.scalar(
                    select(ProductVariant).where(ProductVariant.sku == sku)
                )
                if variant is None:
                    variant = ProductVariant(id=uuid.uuid4(), sku=sku, product_id=product.id)
                    session.add(variant)
                variant.options = options
                variant.price_minor_units = (price_kr + variant_index * 300) * 100
                variant.compare_at_minor_units = compare_kr * 100 if compare_kr else None
                variant.vat_rate = Decimal("0.250")
                variant.is_active = True
                await session.flush()

                stock = await session.scalar(
                    select(StockItem).where(StockItem.variant_id == variant.id)
                )
                if stock is None:
                    session.add(
                        StockItem(
                            variant_id=variant.id,
                            warehouse_code="SE-STO",
                            on_hand=[3, 18, 42, 7, 0][(index + variant_index) % 5],
                        )
                    )

        demo_email = "demo@nordmarkt.se"
        user = await session.scalar(select(User).where(User.email == demo_email))
        if user is None:
            user = User(
                email=demo_email,
                password_hash=hash_password("nordmarkt-demo-2026"),
                full_name="Demo Kund",
                roles=["customer", "admin"],
            )
            session.add(user)
            await session.flush()
            session.add(
                Address(
                    user_id=user.id,
                    recipient="Demo Kund",
                    street="Hornsgatan 12",
                    postal_code="118 20",
                    city="Stockholm",
                    is_default=True,
                )
            )

        await session.commit()
        logger.info("seed_complete", products=len(PRODUCTS), categories=len(CATEGORIES))


if __name__ == "__main__":
    asyncio.run(seed())
