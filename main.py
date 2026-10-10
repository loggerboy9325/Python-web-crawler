import asyncio
import sys

from crawl import crawl_site_async
from json_report import write_json_report


async def main():
    # if len(sys.argv) < 2:
    #    print("no website provided")
    #   sys.exit(1)

    #    if len(sys.argv) > 2:
    #       print("too many arguments provided")
    #      sys.exit(1)

    if len(sys.argv) == 4:
        BASE_URL = sys.argv[1]
        print(f"starting crawl of {BASE_URL}")

    page_data = await crawl_site_async(BASE_URL)

    write_json_report(page_data)


#  for page in page_data.values():
#     print(f"{page['url']} {len(page['outgoing_links'])}")


if __name__ == "__main__":
    asyncio.run(main())
